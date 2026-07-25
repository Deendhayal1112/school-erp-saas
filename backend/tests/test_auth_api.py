"""
Integration tests for Phase 3 Step 7 Authentication REST APIs.

Uses httpx.AsyncClient + ASGITransport to exercise the real FastAPI ASGI app,
hitting the full stack (routing → endpoints → service → repository → database).

Seeded data assumed present:
  - 1 School record (demo school)
  - 1 superadmin user: email=admin@demoschool.edu, password=Admin@1234
"""

import uuid
from datetime import timedelta

import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.core import tokens
from app.main import app

BASE = "/api/v1/auth"
SEEDED_EMAIL = "superadmin@schoolerpsaas.com"
SEEDED_PASSWORD = "Admin@1234"


@pytest.fixture
async def client() -> AsyncClient:
    """Builds an async test client wired directly to the ASGI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def auth_tokens(client: AsyncClient) -> dict:
    """Logs in with the seeded superadmin and returns the token pair."""
    resp = await client.post(
        f"{BASE}/login",
        json={"email": SEEDED_EMAIL, "password": SEEDED_PASSWORD},
    )
    assert resp.status_code == 200, f"Seed login failed: {resp.text}"
    return resp.json()


# ==========================================
# LOGIN TESTS
# ==========================================
@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """POST /login with valid credentials returns 200 and full token payload."""
    resp = await client.post(
        f"{BASE}/login",
        json={"email": SEEDED_EMAIL, "password": SEEDED_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert isinstance(body["expires_in"], int)
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """POST /login with wrong password returns 401."""
    resp = await client.post(
        f"{BASE}/login",
        json={"email": SEEDED_EMAIL, "password": "WrongPassword99!"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert "error" in body


@pytest.mark.asyncio
async def test_login_invalid_email(client: AsyncClient):
    """POST /login with non-existent email returns 401."""
    resp = await client.post(
        f"{BASE}/login",
        json={"email": "nobody@unknown.edu", "password": "Password123!"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_login_malformed_email_format(client: AsyncClient):
    """POST /login with malformed email string returns 422 validation error."""
    resp = await client.post(
        f"{BASE}/login",
        json={"email": "not-an-email", "password": "Password123!"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "ValidationError"


@pytest.mark.asyncio
async def test_login_short_password(client: AsyncClient):
    """POST /login with a sub-8 char password returns 422 validation error."""
    resp = await client.post(
        f"{BASE}/login",
        json={"email": SEEDED_EMAIL, "password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_missing_fields(client: AsyncClient):
    """POST /login with empty body returns 422 validation error."""
    resp = await client.post(f"{BASE}/login", json={})
    assert resp.status_code == 422


# ==========================================
# TOKEN REFRESH TESTS
# ==========================================
@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, auth_tokens: dict):
    """POST /refresh with valid refresh token returns 200 and new tokens."""
    resp = await client.post(
        f"{BASE}/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    """POST /refresh with a garbage token returns 401."""
    resp = await client.post(
        f"{BASE}/refresh",
        json={"refresh_token": "this.is.not.a.valid.jwt"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_refresh_access_token_rejected(client: AsyncClient, auth_tokens: dict):
    """POST /refresh with an access token (wrong type) returns 401."""
    resp = await client.post(
        f"{BASE}/refresh",
        json={"refresh_token": auth_tokens["access_token"]},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_refresh_expired_token(client: AsyncClient):
    """POST /refresh with an already-expired refresh token returns 401."""
    expired = tokens.create_refresh_token(
        subject=str(uuid.uuid4()), expires_delta=timedelta(seconds=-10)
    )
    resp = await client.post(
        f"{BASE}/refresh",
        json={"refresh_token": expired},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_refresh_missing_field(client: AsyncClient):
    """POST /refresh with empty body returns 422."""
    resp = await client.post(f"{BASE}/refresh", json={})
    assert resp.status_code == 422


# ==========================================
# LOGOUT TESTS
# ==========================================
@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, auth_tokens: dict):
    """POST /logout with valid Bearer token returns 200 success response."""
    resp = await client.post(
        f"{BASE}/logout",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "logged out" in body["message"].lower()


@pytest.mark.asyncio
async def test_logout_missing_token(client: AsyncClient):
    """POST /logout with no Authorization header returns 401."""
    resp = await client.post(f"{BASE}/logout")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalid_token(client: AsyncClient):
    """POST /logout with a malformed Bearer token returns 401."""
    resp = await client.post(
        f"{BASE}/logout",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401


# ==========================================
# GET /me (CURRENT USER) TESTS
# ==========================================
@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient, auth_tokens: dict):
    """GET /me with valid Bearer token returns 200 and user profile."""
    resp = await client.get(
        f"{BASE}/me",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "email" in body
    assert "full_name" in body
    assert "role" in body
    assert "is_active" in body
    # Sensitive fields must NOT be exposed
    assert "password_hash" not in body
    assert "password" not in body
    assert "refresh_token" not in body


@pytest.mark.asyncio
async def test_get_me_missing_token(client: AsyncClient):
    """GET /me with no Authorization header returns 401."""
    resp = await client.get(f"{BASE}/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    """GET /me with a malformed JWT returns 401."""
    resp = await client.get(
        f"{BASE}/me",
        headers={"Authorization": "Bearer this.is.garbage"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_expired_token(client: AsyncClient):
    """GET /me with an already-expired access token returns 401."""
    expired = tokens.create_access_token(
        subject="00000000-0000-0000-0000-000000000001",
        expires_delta=timedelta(seconds=-10),
    )
    resp = await client.get(
        f"{BASE}/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_unknown_user_token(client: AsyncClient):
    """GET /me with a valid JWT for a non-existent user ID returns 401."""
    ghost_token = tokens.create_access_token(subject=str(uuid.uuid4()))
    resp = await client.get(
        f"{BASE}/me",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )
    assert resp.status_code == 401
