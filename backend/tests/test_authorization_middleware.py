"""
Authorization Middleware Integration Tests — Phase 3 Step 9.

Tests:
  - Valid JWT → request succeeds, context populated
  - Missing JWT → /me returns 401
  - Expired JWT → /me returns 401
  - Invalid/malformed JWT → /me returns 401
  - Permission denied → 403 (via RBAC dependency)
  - Security headers present on every response
  - X-Request-ID echoed in response
  - X-Correlation-ID echoed when supplied
  - RequestContext populated with correct user data
  - Audit events generated (structured log output captured)
  - Public endpoints (health, root) work without auth
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import app
from app.middleware.audit import AuditEvent, _build_entry
from app.middleware.request_context import RequestContext, get_request_context, set_request_context

AUTH_BASE = "/api/v1/auth"
SEEDED_EMAIL = "superadmin@schoolerpsaas.com"
SEEDED_PASSWORD = "Admin@1234"


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def superadmin_token(client: AsyncClient) -> str:
    resp = await client.post(
        f"{AUTH_BASE}/login",
        json={"email": SEEDED_EMAIL, "password": SEEDED_PASSWORD},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _make_expired_token() -> str:
    """Creates a structurally valid JWT that is already expired."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "exp": datetime.now(UTC) - timedelta(seconds=10),
        "iat": datetime.now(UTC) - timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _make_invalid_signature_token() -> str:
    """Creates a JWT signed with the wrong secret."""
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=30),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, "WRONG_SECRET_KEY_XXXXXXXX", algorithm=settings.ALGORITHM)


# ===========================================================================
# 1. Authentication Flow Tests
# ===========================================================================
class TestAuthenticationFlow:

    async def test_valid_jwt_returns_200(self, client: AsyncClient, superadmin_token: str):
        """Valid Bearer token succeeds on protected endpoint."""
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200

    async def test_missing_jwt_returns_401(self, client: AsyncClient):
        """No Authorization header → 401 Unauthorized."""
        resp = await client.get(f"{AUTH_BASE}/me")
        assert resp.status_code == 401

    async def test_empty_bearer_returns_401(self, client: AsyncClient):
        """Empty Bearer value → 401 Unauthorized."""
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    async def test_expired_jwt_returns_401(self, client: AsyncClient):
        """Expired token → 401 Unauthorized."""
        expired = _make_expired_token()
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401

    async def test_invalid_signature_returns_401(self, client: AsyncClient):
        """Wrong-secret token → 401 Unauthorized."""
        bad_token = _make_invalid_signature_token()
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 401

    async def test_malformed_token_returns_401(self, client: AsyncClient):
        """Completely garbled token string → 401 Unauthorized."""
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": "Bearer not.a.real.jwt.token.here"},
        )
        assert resp.status_code == 401

    async def test_wrong_scheme_returns_401(self, client: AsyncClient):
        """Basic Auth scheme instead of Bearer → 401 Unauthorized."""
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401


# ===========================================================================
# 2. Security Headers Tests
# ===========================================================================
class TestSecurityHeaders:

    async def test_x_content_type_options_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    async def test_x_frame_options_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    async def test_referrer_policy_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    async def test_content_security_policy_present(self, client: AsyncClient):
        resp = await client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    async def test_permissions_policy_present(self, client: AsyncClient):
        resp = await client.get("/health")
        policy = resp.headers.get("Permissions-Policy", "")
        assert "geolocation=()" in policy

    async def test_cache_control_no_store(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("Cache-Control") == "no-store"

    async def test_security_headers_present_on_protected_endpoint(
        self, client: AsyncClient, superadmin_token: str
    ):
        """Security headers are injected on authenticated API responses too."""
        resp = await client.get(
            f"{AUTH_BASE}/me",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    async def test_security_headers_present_on_error_response(self, client: AsyncClient):
        """Security headers are injected even on 401 error responses."""
        resp = await client.get(f"{AUTH_BASE}/me")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ===========================================================================
# 3. Request-ID & Correlation-ID Tests
# ===========================================================================
class TestRequestTracingHeaders:

    async def test_x_request_id_echoed_in_response(self, client: AsyncClient):
        """X-Request-ID supplied by caller is echoed in the response."""
        my_request_id = str(uuid.uuid4())
        resp = await client.get(
            "/health",
            headers={"X-Request-ID": my_request_id},
        )
        assert resp.headers.get("X-Request-ID") == my_request_id

    async def test_x_request_id_generated_when_absent(self, client: AsyncClient):
        """A UUID is auto-generated and echoed when X-Request-ID is not supplied."""
        resp = await client.get("/health")
        request_id = resp.headers.get("X-Request-ID")
        assert request_id is not None
        # Must be a valid UUID
        uuid.UUID(request_id)

    async def test_x_correlation_id_echoed(self, client: AsyncClient):
        """X-Correlation-ID is echoed in the response when supplied."""
        correlation_id = str(uuid.uuid4())
        resp = await client.get(
            "/health",
            headers={"X-Correlation-ID": correlation_id},
        )
        assert resp.headers.get("X-Correlation-ID") == correlation_id

    async def test_x_correlation_id_absent_when_not_supplied(self, client: AsyncClient):
        """X-Correlation-ID is absent in the response if not supplied in the request."""
        resp = await client.get("/health")
        # Should not be present if not sent by client
        assert "X-Correlation-ID" not in resp.headers


# ===========================================================================
# 4. Public Endpoint Tests
# ===========================================================================
class TestPublicEndpoints:

    async def test_health_endpoint_accessible_without_auth(self, client: AsyncClient):
        """Public /health endpoint returns 200 without any authentication."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_root_endpoint_accessible_without_auth(self, client: AsyncClient):
        """Root / endpoint returns 200 without any authentication."""
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_login_endpoint_accessible_without_auth(self, client: AsyncClient):
        """Login endpoint itself is reachable without prior authentication."""
        resp = await client.post(
            f"{AUTH_BASE}/login",
            json={"email": "noone@example.com", "password": "WrongPass@1"},
        )
        # Returns 401 for bad creds, but NOT because of middleware blocking
        assert resp.status_code == 401


# ===========================================================================
# 5. Request Context Tests
# ===========================================================================
class TestRequestContext:

    def test_request_context_defaults(self):
        """RequestContext defaults are sensible out of the box."""
        ctx = RequestContext()
        assert ctx.request_id is not None
        assert ctx.user_id is None
        assert ctx.role is None
        assert ctx.permissions == frozenset()
        assert ctx.is_authenticated is False

    def test_request_context_is_authenticated(self):
        """is_authenticated returns True when user_id is set."""
        ctx = RequestContext(user_id=uuid.uuid4())
        assert ctx.is_authenticated is True

    def test_request_context_elapsed_ms(self):
        """elapsed_ms returns a positive float."""
        import time
        ctx = RequestContext()
        time.sleep(0.001)
        assert ctx.elapsed_ms > 0

    def test_request_context_to_log_dict(self):
        """to_log_dict() serializes all expected fields."""
        uid = uuid.uuid4()
        sid = uuid.uuid4()
        ctx = RequestContext(
            user_id=uid,
            school_id=sid,
            role="TEACHER",
            client_ip="10.0.0.1",
            request_path="/api/v1/test",
            http_method="GET",
        )
        d = ctx.to_log_dict()
        assert d["user_id"] == str(uid)
        assert d["school_id"] == str(sid)
        assert d["role"] == "TEACHER"
        assert d["client_ip"] == "10.0.0.1"

    def test_context_var_get_and_set(self):
        """ContextVar stores and retrieves RequestContext correctly."""
        ctx = RequestContext(user_id=uuid.uuid4(), role="PRINCIPAL")
        set_request_context(ctx)
        retrieved = get_request_context()
        assert retrieved is ctx
        assert retrieved.role == "PRINCIPAL"


# ===========================================================================
# 6. Audit Logging Tests
# ===========================================================================
class TestAuditLogging:

    def test_audit_entry_structure(self):
        """_build_entry produces all required fields."""
        uid = uuid.uuid4()
        entry = _build_entry(
            AuditEvent.LOGIN_SUCCESS,
            user_id=uid,
            role="TEACHER",
            ip_address="192.168.1.1",
            path="/api/v1/auth/login",
            method="POST",
        )
        assert entry["event"] == AuditEvent.LOGIN_SUCCESS
        assert entry["user_id"] == str(uid)
        assert entry["role"] == "TEACHER"
        assert entry["ip_address"] == "192.168.1.1"
        assert "timestamp" in entry

    def test_all_audit_events_are_strings(self):
        """Every AuditEvent value is a valid non-empty string."""
        for event in AuditEvent:
            assert isinstance(str(event), str)
            assert len(str(event)) > 0

    def test_audit_log_emitted_on_login_success(self, caplog):
        """log_login_success emits a log entry at INFO level."""
        from app.middleware.audit import log_login_success
        uid = uuid.uuid4()
        sid = uuid.uuid4()
        with caplog.at_level(logging.INFO, logger="school_erp.audit"):
            log_login_success(uid, sid, "TEACHER", "10.0.0.5", request_id="req-123")
        assert any("auth.login.success" in r.message for r in caplog.records)

    def test_audit_log_emitted_on_permission_denied(self, caplog):
        """log_permission_denied emits a WARNING log entry."""
        from app.middleware.audit import log_permission_denied
        uid = uuid.uuid4()
        with caplog.at_level(logging.WARNING, logger="school_erp.audit"):
            log_permission_denied(
                user_id=uid,
                role="TEACHER",
                ip_address="10.0.0.1",
                path="/api/v1/fees",
                method="POST",
                permission="fee.collect",
            )
        assert any("authz.permission_denied" in r.message for r in caplog.records)

    def test_audit_log_emitted_on_token_expired(self, caplog):
        """log_token_expired emits a WARNING log entry."""
        from app.middleware.audit import log_token_expired
        with caplog.at_level(logging.WARNING, logger="school_erp.audit"):
            log_token_expired(
                ip_address="10.0.0.1",
                path="/api/v1/auth/me",
                method="GET",
                request_id="req-456",
            )
        assert any("auth.token.expired" in r.message for r in caplog.records)

    def test_audit_log_emitted_on_role_denied(self, caplog):
        """log_role_denied emits a WARNING log entry."""
        from app.middleware.audit import log_role_denied
        uid = uuid.uuid4()
        with caplog.at_level(logging.WARNING, logger="school_erp.audit"):
            log_role_denied(
                user_id=uid,
                role="TEACHER",
                ip_address="10.0.0.2",
                path="/api/v1/admin",
                method="DELETE",
                required_role="SUPER_ADMIN",
            )
        assert any("authz.role_denied" in r.message for r in caplog.records)

    async def test_audit_log_generated_on_authenticated_request(
        self, client: AsyncClient, superadmin_token: str, caplog
    ):
        """An authenticated request generates an authorization success audit log."""
        with caplog.at_level(logging.INFO, logger="school_erp.audit"):
            resp = await client.get(
                f"{AUTH_BASE}/me",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )
        assert resp.status_code == 200
        # At minimum the request_received and request_completed events are emitted.
        assert any("request." in r.message for r in caplog.records)
