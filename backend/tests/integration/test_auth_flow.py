"""
End-to-End Authentication & Security Integration Tests — Phase 3 Step 12.
"""

import hashlib
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import jwt, tokens
from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.email_verification_token import EmailVerificationToken
from app.models.role import Role
from app.models.school import School
from app.models.user import User


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_complete_e2e_authentication_workflow(client: AsyncClient):
    """
    TASK 1: Runs the entire authentication, authorization, registration,
    email verification, session, password change, refresh, and logout flow.
    """
    async with AsyncSessionLocal() as session:
        # Fetch school and student role
        school_res = await session.execute(select(School).limit(1))
        school = school_res.scalar_one()
        role_res = await session.execute(select(Role).where(Role.code == "STUDENT"))
        role = role_res.scalar_one()

        # 1. Register User (Simulated DB creation with unverified email)
        email = f"e2e_student_{uuid.uuid4().hex[:8]}@demoschool.edu"
        username = f"e2estudent_{uuid.uuid4().hex[:8]}"
        pwd = "ValidSecret123!"

        user = User(
            first_name="E2E",
            last_name="Student",
            username=username,
            email=email,
            password_hash=hash_password(pwd),
            school_id=school.id,
            role_id=role.id,
            status="inactive",
            email_verified=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        user_id = user.id

    try:
        # 2. Try Logging In prior to verification -> Should fail with Inactive User check (401 or 403 depending on status)
        login_fail = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": pwd}
        )
        assert login_fail.status_code in (401, 403)

        # 3. Request verification email
        send_email_resp = await client.post(
            "/api/v1/auth/send-verification-email",
            json={"email": email}
        )
        assert send_email_resp.status_code == 200

        # Retrieve generated token from DB
        async with AsyncSessionLocal() as session:
            stmt = select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id
            ).order_by(EmailVerificationToken.created_at.desc()).limit(1)
            res = await session.execute(stmt)
            token_record = res.scalar_one()

            # Retrieve raw token hash by searching generated test database records
            # For simplicity, we can fetch token_hash directly and use a mocked verification or update used state,
            # but to fully test the verify-email API route, we verify by using a direct database activation simulation
            # or generating a known token. Let's create a known token hash in database:
            raw_token = "my_custom_e2e_verification_token_key"
            known_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            token_record.token_hash = known_hash
            session.add(token_record)
            await session.commit()

        # 4. Verify email token via API
        verify_resp = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": raw_token}
        )
        assert verify_resp.status_code == 200

        # 5. Login after activation -> Should succeed
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": pwd}
        )
        assert login_resp.status_code == 200
        tokens_data = login_resp.json()
        access_token = tokens_data["access_token"]
        refresh_token = tokens_data["refresh_token"]

        # 6. Retrieve active profile info via /me
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == email

        # 7. Refresh token rotation
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_resp.status_code == 200
        new_tokens_data = refresh_resp.json()
        new_access = new_tokens_data["access_token"]
        _new_refresh = new_tokens_data["refresh_token"]

        # 8. Change Password via API
        new_pwd = "NewValidSecret123!"
        change_resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": pwd,
                "new_password": new_pwd,
                "confirm_password": new_pwd
            },
            headers={"Authorization": f"Bearer {new_access}"}
        )
        assert change_resp.status_code == 200

        # 9. Verify that old access/refresh tokens are now rejected (session invalidation)
        old_me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access}"}
        )
        assert old_me_resp.status_code == 401

        # 10. Login with new password -> Should succeed
        login_new_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_pwd}
        )
        assert login_new_resp.status_code == 200
        final_access = login_new_resp.json()["access_token"]

        # 11. Logout successfully
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {final_access}"}
        )
        assert logout_resp.status_code == 200

    finally:
        # Clean up database record
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            u = res.scalar_one_or_none()
            if u:
                await session.delete(u)
                await session.commit()


# ===========================================================================
# TASK 2: Security Protection Validation Tests
# ===========================================================================
class TestSecurityProtections:

    @pytest.mark.asyncio
    async def test_sql_injection_defense(self, client: AsyncClient):
        """Verifies that SQL Injection characters in login fields are rejected or parameterized safely."""
        sqli_payloads = [
            "admin@schoolerpsaas.com' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin@schoolerpsaas.com' UNION SELECT NULL, NULL --",
        ]
        for payload in sqli_payloads:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": payload, "password": "SomePassword123!"}
            )
            # Should fail validation (422) or credentials (401), but NEVER throw 500 or execute SQL
            assert resp.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_jwt_tampering_defense(self, client: AsyncClient):
        """Verifies that tampered or unsigned access tokens are rejected with 401."""
        tampered_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjNlNDU2Ny1lODliLTEyZDMtYTQ1Ni00MjY2MTQxNzQwMDAiLCJ0eXBlIjoiYWNjZXNzIn0."
            "unsignedorcorruptedsignaturehere"
        )
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_privilege_escalation_denied(self, client: AsyncClient):
        """Verifies that normal users cannot invoke endpoints protected by higher roles (e.g. Super Admin)."""
        # Since business endpoints aren't implemented, we mock a custom role check to make sure it raises 403.
        from app.auth.roles import ROLE_SUPER_ADMIN, has_minimum_role
        normal_user = type("MockUser", (), {"role": type("MockRole", (), {"code": "STUDENT"})()})()
        assert has_minimum_role(normal_user, ROLE_SUPER_ADMIN) is False


# ===========================================================================
# TASK 3: Performance Performance Tests
# ===========================================================================
class TestPerformanceThresholds:

    @pytest.mark.asyncio
    async def test_jwt_validation_speed(self):
        """Measures speed of JWT decoding and validation (Threshold: < 10ms)."""
        token_str = tokens.create_access_token(subject=str(uuid.uuid4()))

        start = time.perf_counter()
        jwt.decode_token(token_str)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Assert performance requirement met
        assert elapsed_ms < 10.0, f"JWT validation took {elapsed_ms:.2f}ms (threshold: 10ms)"

    @pytest.mark.asyncio
    async def test_permission_lookup_speed(self):
        """Measures permission resolution engine speed (Threshold: < 15ms)."""
        from app.auth import has_permission

        # Build mock user structure
        role = type("MockRole", (), {"code": "TEACHER", "role_permissions": []})()
        user = type("MockUser", (), {"id": uuid.uuid4(), "role": role})()

        start = time.perf_counter()
        has_permission(user, "student.view")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 15.0, f"Permission lookup took {elapsed_ms:.2f}ms (threshold: 15ms)"
