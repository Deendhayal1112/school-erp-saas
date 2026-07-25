"""
Password Management Integration Tests — Phase 3 Step 10.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.exceptions import InvalidCredentialsException
from app.main import app
from app.models.password_reset_token import PasswordResetToken
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.modules.auth.password.exceptions import (
    AccountLockedException,
    ExpiredResetTokenException,
    InvalidCurrentPasswordException,
    PasswordReuseException,
    PasswordValidationError,
)
from app.modules.auth.password.service import PasswordService
from app.repositories.user_repository import UserRepository
from app.services.authentication_service import AuthenticationService


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def test_user():
    """Seeds a temporary user record for integration tests."""
    async with AsyncSessionLocal() as session:
        # Fetch school and role
        school_stmt = select(School).limit(1)
        school_res = await session.execute(school_stmt)
        school = school_res.scalar_one()

        role_stmt = select(Role).where(Role.code == "STUDENT")
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one()

        email = f"pwd_test_{uuid.uuid4().hex[:8]}@demoschool.edu"
        username = f"pwdtest_{uuid.uuid4().hex[:8]}"
        initial_password = "ValidSecret123!"

        user = User(
            first_name="Password",
            last_name="Tester",
            username=username,
            email=email,
            password_hash=hash_password(initial_password),
            school_id=school.id,
            role_id=role.id,
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    yield {
        "id": user.id,
        "email": email,
        "username": username,
        "password": initial_password,
    }

    # Cleanup after test runs
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user.id)
        res = await session.execute(stmt)
        u = res.scalar_one_or_none()
        if u:
            await session.delete(u)
            await session.commit()


@pytest.mark.asyncio
async def test_change_password_success(test_user):
    """Verifies that user can change password successfully when current password matches."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)
        auth_service = AuthenticationService(UserRepository(session))

        # 1. Change password
        new_pwd = "NewValidSec123!"
        await pwd_service.change_password(
            user_id=test_user["id"],
            current_password=test_user["password"],
            new_password=new_pwd,
        )

        # 2. Verify we can authenticate with the new password
        auth_res = await auth_service.authenticate_user(test_user["email"], new_pwd)
        assert auth_res["access_token"] is not None


@pytest.mark.asyncio
async def test_change_password_wrong_current(test_user):
    """Verifies that changing password fails if the current password is wrong."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)

        with pytest.raises(InvalidCurrentPasswordException):
            await pwd_service.change_password(
                user_id=test_user["id"],
                current_password="WrongSecret123!",
                new_password="NewValidSec123!",
            )


@pytest.mark.asyncio
async def test_change_password_weak_policy(test_user):
    """Verifies that weak passwords fail policy check."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)

        # Missing uppercase and numbers, too short
        with pytest.raises(PasswordValidationError):
            await pwd_service.change_password(
                user_id=test_user["id"],
                current_password=test_user["password"],
                new_password="weak",
            )


@pytest.mark.asyncio
async def test_password_reuse_blocking(test_user):
    """Verifies that the user cannot reuse recent passwords."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)

        # Try to change password to the same password
        with pytest.raises(PasswordReuseException):
            await pwd_service.change_password(
                user_id=test_user["id"],
                current_password=test_user["password"],
                new_password=test_user["password"],
            )

        # Change to new password first
        new_pwd1 = "NewSecret123!"
        await pwd_service.change_password(
            user_id=test_user["id"],
            current_password=test_user["password"],
            new_password=new_pwd1,
        )

        # Attempt to change it back to the original password
        with pytest.raises(PasswordReuseException):
            await pwd_service.change_password(
                user_id=test_user["id"],
                current_password=new_pwd1,
                new_password=test_user["password"],
            )


@pytest.mark.asyncio
async def test_forgot_password_and_reset_flow(test_user):
    """Verifies forgot-password generates reset link and reset-password accepts it."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)
        auth_service = AuthenticationService(UserRepository(session))

        # 1. Forgot password
        raw_token = await pwd_service.generate_reset_token(test_user["email"])
        assert raw_token is not None

        # 2. Reset password using token
        new_pwd = "ResetSecret123!"
        await pwd_service.reset_password(raw_token, new_pwd)

        # 3. Verify login works with new password
        auth_res = await auth_service.authenticate_user(test_user["email"], new_pwd)
        assert auth_res["access_token"] is not None


@pytest.mark.asyncio
async def test_forgot_password_non_existent_email():
    """Forgot password for non-existent email should return safely (silent success/enumeration defense)."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)
        # Should not throw any exceptions
        raw_token = await pwd_service.generate_reset_token("nonexistent@example.com")
        assert raw_token is not None


@pytest.mark.asyncio
async def test_reset_password_expired_token(test_user):
    """Verifies that expired reset tokens are rejected."""
    async with AsyncSessionLocal() as session:
        pwd_service = PasswordService(session)

        # Generate reset token
        raw_token = await pwd_service.generate_reset_token(test_user["email"])
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Artificially expire the token in database
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
        res = await session.execute(stmt)
        token_record = res.scalar_one()
        token_record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add(token_record)
        await session.commit()

        # Attempt reset
        with pytest.raises(ExpiredResetTokenException):
            await pwd_service.reset_password(raw_token, "AnotherValidSec123!")


@pytest.mark.asyncio
async def test_failed_login_lockout_and_automatic_unlock(test_user):
    """Verifies user account is temporarily locked after N failed logins and auto-unlocks."""
    async with AsyncSessionLocal() as session:
        auth_service = AuthenticationService(UserRepository(session))

        # Fail logins up to threshold (5 attempts)
        for _ in range(settings.ACCOUNT_LOCKOUT_THRESHOLD - 1):
            with pytest.raises(InvalidCredentialsException):
                await auth_service.authenticate_user(
                    test_user["email"], "WrongSecret123!"
                )

        # The 5th attempt triggers lockout
        with pytest.raises(AccountLockedException):
            await auth_service.authenticate_user(test_user["email"], "WrongSecret123!")

        # Subsequent attempts are locked
        with pytest.raises(AccountLockedException):
            await auth_service.authenticate_user(
                test_user["email"], test_user["password"]
            )

        # Simulate automatic unlock by setting locked_until in the past
        stmt = select(User).where(User.id == test_user["id"])
        res = await session.execute(stmt)
        user = res.scalar_one()
        user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        session.add(user)
        await session.commit()

        # Try authenticating again — should unlock automatically and succeed
        auth_res = await auth_service.authenticate_user(
            test_user["email"], test_user["password"]
        )
        assert auth_res["access_token"] is not None


@pytest.mark.asyncio
async def test_active_tokens_invalidated_by_password_change(
    client: AsyncClient, test_user
):
    """Verifies that previously active access/refresh tokens are invalidated once password is changed."""
    # 1. Login to get tokens
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert login_resp.status_code == 200
    tokens_data = login_resp.json()
    access_token = tokens_data["access_token"]
    refresh_token = tokens_data["refresh_token"]

    # 2. Access /me endpoint — should succeed
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200

    # 3. Change password
    new_pwd = "UpdatedSec123!"
    change_resp = await client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": test_user["password"],
            "new_password": new_pwd,
            "confirm_password": new_pwd,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert change_resp.status_code == 200

    # 4. Attempt to access /me with the old access token — should be rejected
    me_resp_after = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp_after.status_code == 401

    # 5. Attempt to use old refresh token — should be rejected
    refresh_resp_after = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp_after.status_code == 401
