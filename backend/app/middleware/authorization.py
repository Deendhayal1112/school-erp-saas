"""
Authorization & Security Headers Middleware.

Two Starlette ASGI middlewares are implemented here:

  1. RequestContextMiddleware
     Runs first (outermost). Creates a RequestContext for each request,
     populates basic request metadata, and stores it in the ContextVar.

  2. SecurityHeadersMiddleware
     Injects hardened HTTP security headers into every response:
       - X-Request-ID            Unique per-request tracing ID
       - X-Correlation-ID        Caller-supplied distributed trace ID (echoed)
       - X-Content-Type-Options  Prevents MIME-sniffing
       - X-Frame-Options         Prevents clickjacking
       - Referrer-Policy         Controls referrer information leakage
       - Content-Security-Policy Default restrictive CSP policy
       - Strict-Transport-Security  Forces HTTPS (only in production)
       - Permissions-Policy      Limits browser feature access

  3. AuthorizationAuditMiddleware
     Wraps every request. Extracts the JWT token (if present), validates it,
     loads the user from the database, populates the RequestContext with auth
     metadata, and emits structured audit log entries.

     This middleware does NOT reject unauthenticated requests — that remains the
     responsibility of the FastAPI dependency layer (get_current_user / RBAC
     dependencies). Its job is context enrichment and audit logging only.

Architecture notes:
  - Middleware is ASGI-level, runs before FastAPI routing.
  - Auth rejection still happens in FastAPI Depends() — middleware only enriches.
  - All DB I/O uses async SQLAlchemy sessions opened per-request.
  - Token errors are logged and silently absorbed (no middleware-level 401).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.jwt import (
    MalformedTokenError,
    MissingClaimsError,
    TokenExpiredError,
    decode_token,
)
from app.middleware import audit as audit_log
from app.middleware.request_context import RequestContext, set_request_context

logger = logging.getLogger(__name__)

# Routes that are completely public — no auth context enrichment needed.
_PUBLIC_PATHS: set[str] = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# ===========================================================================
# OWASP-recommended security header values
# ===========================================================================
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
    "Permissions-Policy": (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
    ),
    "X-Permitted-Cross-Domain-Policies": "none",
    "Cache-Control": "no-store",
}

_HSTS_HEADER: str = "max-age=63072000; includeSubDomains; preload"


def _extract_client_ip(request: Request) -> str:
    """Extracts the best-effort real IP from X-Forwarded-For or connection info."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _extract_bearer_token(request: Request) -> str | None:
    """Parses the Authorization header and returns the raw token string, or None."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer ") and len(header) > 7:
        return header[7:].strip()
    return None


# ===========================================================================
# 1. RequestContextMiddleware
# ===========================================================================
class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Outermost middleware. Creates a RequestContext for every request and
    stores it in the ContextVar before delegating to the next layer.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID")
        client_ip = _extract_client_ip(request)
        timezone = request.headers.get("X-Timezone") or "UTC"
        language = request.headers.get("Accept-Language") or "en"
        if language and "," in language:
            language = language.split(",")[0].split(";")[0].strip()

        ctx = RequestContext(
            request_id=request_id,
            correlation_id=correlation_id,
            client_ip=client_ip,
            request_path=request.url.path,
            http_method=request.method,
            timezone=timezone,
            language=language,
        )
        set_request_context(ctx)

        audit_log.log_request_received(
            ip_address=client_ip,
            path=request.url.path,
            method=request.method,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        start = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000

        audit_log.log_request_completed(
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            elapsed_ms=elapsed,
            request_id=request_id,
        )

        return response


# ===========================================================================
# 2. SecurityHeadersMiddleware
# ===========================================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects OWASP-recommended security response headers into every response.
    Also echoes X-Request-ID and X-Correlation-ID so callers can trace requests.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.middleware.request_context import get_request_context

        response = await call_next(request)

        if not settings.ENABLE_SECURITY_HEADERS:
            return response

        # Inject static security headers
        for header, value in _SECURITY_HEADERS.items():
            if header == "Content-Security-Policy" and (
                request.url.path.startswith("/docs") or
                request.url.path.startswith("/redoc") or
                request.url.path.startswith("/openapi.json")
            ):
                response.headers[header] = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                    "img-src 'self' data: fastly.jsdelivr.net cdn.jsdelivr.net; "
                    "font-src 'self'; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none';"
                )
            else:
                response.headers[header] = value

        # HSTS only in production (HTTPS guaranteed)
        if settings.ENV == "production":
            response.headers["Strict-Transport-Security"] = _HSTS_HEADER

        # Echo tracing headers from context
        ctx = get_request_context()
        if ctx:
            response.headers["X-Request-ID"] = ctx.request_id
            if ctx.correlation_id:
                response.headers["X-Correlation-ID"] = ctx.correlation_id

        return response


# ===========================================================================
# 3. AuthorizationAuditMiddleware
# ===========================================================================
class AuthorizationAuditMiddleware(BaseHTTPMiddleware):
    """
    JWT validation and request context enrichment middleware.

    For every request that carries a Bearer token:
      1. Decodes and validates the token.
      2. Loads the User from the database.
      3. Populates the RequestContext with user_id, school_id, role, permissions.
      4. Emits a structured audit log entry.

    Token failures (expired, invalid) are logged but NOT rejected here.
    Rejection is the responsibility of FastAPI's dependency layer.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.ENABLE_AUTHORIZATION_MIDDLEWARE:
            return await call_next(request)

        from app.middleware.request_context import get_request_context

        ctx = get_request_context()
        client_ip = ctx.client_ip if ctx else _extract_client_ip(request)
        request_id = ctx.request_id if ctx else None
        correlation_id = ctx.correlation_id if ctx else None
        path = request.url.path
        method = request.method

        token = _extract_bearer_token(request)

        if token:
            await self._process_token(
                request=request,
                token=token,
                ctx=ctx,
                client_ip=client_ip,
                request_id=request_id,
                correlation_id=correlation_id,
                path=path,
                method=method,
            )

        return await call_next(request)

    async def _process_token(
        self,
        request: Request,
        token: str,
        ctx: RequestContext | None,
        client_ip: str | None,
        request_id: str | None,
        correlation_id: str | None,
        path: str,
        method: str,
    ) -> None:
        """Decodes the token, loads the user, and enriches the RequestContext."""
        try:
            payload = decode_token(token)
        except TokenExpiredError:
            audit_log.log_token_expired(
                ip_address=client_ip, path=path, method=method, request_id=request_id
            )
            return
        except (MalformedTokenError, MissingClaimsError) as exc:
            audit_log.log_token_validation_failure(
                ip_address=client_ip,
                path=path,
                method=method,
                detail=str(exc),
                request_id=request_id,
                correlation_id=correlation_id,
            )
            return
        except Exception as exc:
            audit_log.log_authentication_failure(
                ip_address=client_ip,
                path=path,
                method=method,
                detail=str(exc),
                request_id=request_id,
                correlation_id=correlation_id,
            )
            return

        # Only process access tokens — not refresh tokens
        if payload.get("type") != "access":
            return

        try:
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError):
            return

        # Lazily load user + relationships from DB
        try:
            from app.auth.permissions import _extract_permission_codes
            from app.auth.roles import get_user_role
            from app.db.database import get_db
            from app.repositories.user_repository import UserRepository

            # Obtain an async session without depending on FastAPI's Depends()
            async for db in get_db():
                user_repo = UserRepository(db)
                user = await user_repo.get_by_id(user_id)
                if not user or user.is_deleted:
                    return

                # Invalidate if password changed since token issuance
                from datetime import datetime
                iat_timestamp = payload.get("iat")
                if iat_timestamp and user.password_changed_at:
                    token_iat_dt = datetime.fromtimestamp(iat_timestamp, tz=UTC)
                    if token_iat_dt < user.password_changed_at.replace(microsecond=0):
                        audit_log.log_token_validation_failure(
                            ip_address=client_ip,
                            path=path,
                            method=method,
                            detail="Token has been invalidated by a password change",
                            request_id=request_id,
                            correlation_id=correlation_id,
                        )
                        return

                school_id = user.school_id if hasattr(user, "school_id") else None
                role_code = get_user_role(user)
                permissions = _extract_permission_codes(user)

                if ctx is not None:
                    ctx.user_id = user.id
                    ctx.school_id = school_id
                    ctx.role = role_code
                    ctx.permissions = permissions

                audit_log.log_authorization_success(
                    user_id=user.id,
                    school_id=school_id,
                    role=role_code,
                    ip_address=client_ip,
                    path=path,
                    method=method,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
                break  # only one session needed

        except Exception as exc:
            logger.warning(
                "AuthorizationAuditMiddleware: context enrichment failed: %s", exc
            )
