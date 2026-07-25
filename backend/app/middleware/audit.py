"""
Authorization Audit Logger.

Emits structured, JSON-compatible audit log entries for every security-relevant
event in the request lifecycle.  Uses Python's standard logging module so that
the output backend (stdout, file, cloud sink) is determined by configuration.

Each event carries:
  - timestamp (ISO-8601 UTC)
  - event type
  - user_id, school_id, role
  - IP address
  - HTTP method + path
  - request_id / correlation_id

This module deliberately has NO external dependencies beyond stdlib so that it
can be used from middleware before the database session is available.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from app.core.config import settings

# Dedicated audit logger — configure its handler in core/logger.py if needed.
audit_logger = logging.getLogger("school_erp.audit")


class AuditEvent(StrEnum):
    """Canonical audit event type identifiers."""

    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_VALIDATION_FAILURE = "auth.token.invalid"
    TOKEN_EXPIRED = "auth.token.expired"
    AUTHENTICATION_FAILURE = "auth.failure"

    # Authorization events
    AUTHORIZATION_SUCCESS = "authz.success"
    PERMISSION_DENIED = "authz.permission_denied"
    ROLE_DENIED = "authz.role_denied"
    FORBIDDEN = "authz.forbidden"

    # Request lifecycle
    REQUEST_RECEIVED = "request.received"
    REQUEST_COMPLETED = "request.completed"


def _build_entry(
    event: AuditEvent,
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    user_id: uuid.UUID | str | None = None,
    school_id: uuid.UUID | str | None = None,
    role: str | None = None,
    ip_address: str | None = None,
    path: str | None = None,
    method: str | None = None,
    detail: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Assembles a structured audit log record dictionary."""
    entry: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": str(event),
        "request_id": request_id,
        "correlation_id": correlation_id,
        "user_id": str(user_id) if user_id else None,
        "school_id": str(school_id) if school_id else None,
        "role": role,
        "ip_address": ip_address,
        "path": path,
        "method": method,
    }
    if detail:
        entry["detail"] = detail
    if extra:
        entry.update(extra)
    return entry


def _emit(level: int, entry: dict) -> None:
    """Emits the structured audit entry to the audit logger."""
    if not settings.ENABLE_AUDIT_LOG:
        return
    audit_logger.log(level, json.dumps(entry, default=str))


# ===========================================================================
# Public Audit API
# ===========================================================================
def log_login_success(
    user_id: uuid.UUID,
    school_id: uuid.UUID | None,
    role: str | None,
    ip_address: str | None,
    request_id: str | None = None,
) -> None:
    _emit(
        logging.INFO,
        _build_entry(
            AuditEvent.LOGIN_SUCCESS,
            request_id=request_id,
            user_id=user_id,
            school_id=school_id,
            role=role,
            ip_address=ip_address,
        ),
    )


def log_login_failure(
    ip_address: str | None,
    path: str | None = None,
    detail: str | None = None,
    request_id: str | None = None,
) -> None:
    _emit(
        logging.WARNING,
        _build_entry(
            AuditEvent.LOGIN_FAILURE,
            request_id=request_id,
            ip_address=ip_address,
            path=path,
            detail=detail,
        ),
    )


def log_logout(
    user_id: uuid.UUID,
    ip_address: str | None,
    request_id: str | None = None,
) -> None:
    _emit(
        logging.INFO,
        _build_entry(
            AuditEvent.LOGOUT,
            request_id=request_id,
            user_id=user_id,
            ip_address=ip_address,
        ),
    )


def log_token_validation_failure(
    ip_address: str | None,
    path: str | None,
    method: str | None,
    detail: str | None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    _emit(
        logging.WARNING,
        _build_entry(
            AuditEvent.TOKEN_VALIDATION_FAILURE,
            request_id=request_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            path=path,
            method=method,
            detail=detail,
        ),
    )


def log_token_expired(
    ip_address: str | None,
    path: str | None,
    method: str | None,
    request_id: str | None = None,
) -> None:
    _emit(
        logging.WARNING,
        _build_entry(
            AuditEvent.TOKEN_EXPIRED,
            request_id=request_id,
            ip_address=ip_address,
            path=path,
            method=method,
            detail="JWT access token has expired.",
        ),
    )


def log_authentication_failure(
    ip_address: str | None,
    path: str | None,
    method: str | None,
    detail: str | None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    _emit(
        logging.WARNING,
        _build_entry(
            AuditEvent.AUTHENTICATION_FAILURE,
            request_id=request_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            path=path,
            method=method,
            detail=detail,
        ),
    )


def log_authorization_success(
    user_id: uuid.UUID,
    school_id: uuid.UUID | None,
    role: str | None,
    ip_address: str | None,
    path: str | None,
    method: str | None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    _emit(
        logging.INFO,
        _build_entry(
            AuditEvent.AUTHORIZATION_SUCCESS,
            request_id=request_id,
            correlation_id=correlation_id,
            user_id=user_id,
            school_id=school_id,
            role=role,
            ip_address=ip_address,
            path=path,
            method=method,
        ),
    )


def log_permission_denied(
    user_id: uuid.UUID | None,
    role: str | None,
    ip_address: str | None,
    path: str | None,
    method: str | None,
    permission: str,
    request_id: str | None = None,
    school_id: uuid.UUID | None = None,
    correlation_id: str | None = None,
) -> None:
    _emit(
        logging.WARNING,
        _build_entry(
            AuditEvent.PERMISSION_DENIED,
            request_id=request_id,
            correlation_id=correlation_id,
            user_id=user_id,
            school_id=school_id,
            role=role,
            ip_address=ip_address,
            path=path,
            method=method,
            detail=f"Permission denied: '{permission}'",
        ),
    )


def log_role_denied(
    user_id: uuid.UUID | None,
    role: str | None,
    ip_address: str | None,
    path: str | None,
    method: str | None,
    required_role: str,
    request_id: str | None = None,
    school_id: uuid.UUID | None = None,
) -> None:
    _emit(
        logging.WARNING,
        _build_entry(
            AuditEvent.ROLE_DENIED,
            request_id=request_id,
            user_id=user_id,
            school_id=school_id,
            role=role,
            ip_address=ip_address,
            path=path,
            method=method,
            detail=f"Role denied: '{required_role}' required.",
        ),
    )


def log_request_received(
    ip_address: str | None,
    path: str | None,
    method: str | None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    _emit(
        logging.DEBUG,
        _build_entry(
            AuditEvent.REQUEST_RECEIVED,
            request_id=request_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            path=path,
            method=method,
        ),
    )


def log_request_completed(
    path: str | None,
    method: str | None,
    status_code: int,
    elapsed_ms: float,
    request_id: str | None = None,
) -> None:
    _emit(
        logging.INFO,
        _build_entry(
            AuditEvent.REQUEST_COMPLETED,
            request_id=request_id,
            path=path,
            method=method,
            extra={"status_code": status_code, "elapsed_ms": round(elapsed_ms, 2)},
        ),
    )
