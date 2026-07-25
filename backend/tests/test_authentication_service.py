import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import tokens
from app.core.password import hash_password
from app.db.session import AsyncSessionLocal
from app.exceptions import (
    DeletedUserException,
    InactiveSchoolException,
    InactiveUserException,
    InvalidCredentialsException,
    RefreshTokenException,
    TokenExpiredException,
)
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.authentication_service import AuthenticationService


@pytest.mark.asyncio
async def test_authentication_service_flows():
    """
    Integration test verifying successful logins, password failures,
    user/school status restrictions, refresh rotations, and audit updates.
    """
    async with AsyncSessionLocal() as session:
        # 1. Fetch seeded dependencies
        school_stmt = select(School).limit(1)
        school_res = await session.execute(school_stmt)
        school = school_res.scalar_one_or_none()
        assert school is not None, (
            "Database must be seeded with a School record before running tests"
        )

        role_stmt = select(Role).where(Role.code == "TEACHER")
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        assert role is not None, (
            "Database must be seeded with a TEACHER Role record before running tests"
        )

        user_repo = UserRepository(session)
        auth_service = AuthenticationService(user_repo)

        # Declare test parameters
        test_email = f"auth_test_{uuid.uuid4().hex[:8]}@demoschool.edu"
        test_username = f"authtest_{uuid.uuid4().hex[:8]}"
        plain_password = "Password123!"
        hashed_pass = hash_password(plain_password)

        test_user = User(
            first_name="Auth",
            last_name="Tester",
            username=test_username,
            email=test_email,
            password_hash=hashed_pass,
            school_id=school.id,
            role_id=role.id,
            status="active",
        )
        created_user = await user_repo.create_user(test_user)
        await session.commit()

        try:
            # A. Verify Successful login & token creation
            login_response = await auth_service.authenticate_user(
                test_email, plain_password
            )
            assert login_response is not None
            assert "access_token" in login_response
            assert "refresh_token" in login_response
            assert login_response["token_type"] == "bearer"
            assert login_response["expires_in"] > 0

            # Verify last login timestamp was updated
            refreshed_user = await user_repo.get_by_id(created_user.id)
            assert refreshed_user.last_login is not None

            # B. Verify Wrong password rejection
            with pytest.raises(InvalidCredentialsException):
                await auth_service.authenticate_user(test_email, "WrongPassword123!")

            # C. Verify Unknown email rejection
            with pytest.raises(InvalidCredentialsException):
                await auth_service.authenticate_user(
                    "unknown_auth@demoschool.edu", plain_password
                )

            # D. Verify Inactive user status check
            await user_repo.deactivate_user(created_user.id)
            await session.commit()
            with pytest.raises(InactiveUserException):
                await auth_service.authenticate_user(test_email, plain_password)

            # Reactivate for subsequent tests
            await user_repo.activate_user(created_user.id)
            await session.commit()

            # E. Verify Deleted user status check
            await user_repo.soft_delete_user(created_user.id)
            await session.commit()
            with pytest.raises(DeletedUserException):
                await auth_service.authenticate_user(test_email, plain_password)

            # Restore user for subsequent tests
            await user_repo.restore_user(created_user.id)
            await session.commit()

            # F. Verify Inactive school tenant check
            school.is_active = False
            session.add(school)
            await session.commit()
            try:
                with pytest.raises(InactiveSchoolException):
                    await auth_service.authenticate_user(test_email, plain_password)
            finally:
                school.is_active = True
                session.add(school)
                await session.commit()

            # G. Verify Refresh token rotation
            refresh_token = login_response["refresh_token"]
            refresh_response = await auth_service.refresh_access_token(refresh_token)
            assert refresh_response is not None
            assert "access_token" in refresh_response
            assert "refresh_token" in refresh_response

            # H. Verify Expired refresh token rejection
            expired_refresh = tokens.create_refresh_token(
                subject=str(created_user.id), expires_delta=timedelta(seconds=-10)
            )
            with pytest.raises(TokenExpiredException):
                await auth_service.refresh_access_token(expired_refresh)

            # I. Verify Invalid/Corrupted refresh token rejection
            with pytest.raises(RefreshTokenException):
                await auth_service.refresh_access_token(
                    "corrupted_refresh_token_payload"
                )

            # J. Verify Logout signature does not crash
            await auth_service.logout_user(created_user.id)

        finally:
            # Cleanup user record
            await user_repo.delete(created_user)
            await session.commit()
