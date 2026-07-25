import uuid
from datetime import timedelta
import pytest
from fastapi import Request
from sqlalchemy import select

from app.core import tokens
from app.db.session import AsyncSessionLocal
from app.dependencies.auth import (
    AuthenticationRequiredException,
    InactiveAccountException,
    InactiveSchoolException,
    InvalidBearerTokenException,
    TokenExpiredException,
    UserNotFoundException,
)
from app.dependencies.current_user import (
    get_current_active_user,
    get_current_user,
    get_optional_current_user,
)
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.repositories.user_repository import UserRepository


def build_mock_request(headers: dict) -> Request:
    """Builds a mock Request object using Starlette headers mapping structure."""
    scope = {
        "type": "http",
        "headers": [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_auth_dependencies_flows():
    """
    Integration test checking that auth dependency functions retrieve Bearer headers,
    validate formatting details, reject inactive/deleted records, and run optional setups.
    """
    async with AsyncSessionLocal() as session:
        # 1. Fetch seeded dependencies
        school_stmt = select(School).limit(1)
        school_res = await session.execute(school_stmt)
        school = school_res.scalar_one_or_none()
        assert school is not None, "Database must be seeded with a School record before running tests"

        role_stmt = select(Role).where(Role.code == "TEACHER")
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        assert role is not None, "Database must be seeded with a TEACHER Role record before running tests"

        user_repo = UserRepository(session)

        # Define test unique details
        test_email = f"dep_test_{uuid.uuid4().hex[:8]}@demoschool.edu"
        test_username = f"deptest_{uuid.uuid4().hex[:8]}"

        test_user = User(
            first_name="Dep",
            last_name="Tester",
            username=test_username,
            email=test_email,
            password_hash="dummy_hash",
            school_id=school.id,
            role_id=role.id,
            status="active",
        )
        created_user = await user_repo.create_user(test_user)
        await session.commit()

        try:
            # Generate valid access token
            valid_token = tokens.create_access_token(subject=str(created_user.id))

            # A. Verify Successful Authentication
            req = build_mock_request({"Authorization": f"Bearer {valid_token}"})
            user = await get_current_user(req, session)
            assert user.id == created_user.id

            active_user = await get_current_active_user(user)
            assert active_user.id == created_user.id

            # B. Verify Missing Authorization Header throws AuthenticationRequiredException
            req_missing = build_mock_request({})
            with pytest.raises(AuthenticationRequiredException):
                await get_current_user(req_missing, session)

            # C. Verify Invalid Bearer Format throws InvalidBearerTokenException
            req_bad_format = build_mock_request({"Authorization": f"Bearer{valid_token}"})
            with pytest.raises(InvalidBearerTokenException):
                await get_current_user(req_bad_format, session)

            req_bad_scheme = build_mock_request({"Authorization": f"Basic {valid_token}"})
            with pytest.raises(InvalidBearerTokenException):
                await get_current_user(req_bad_scheme, session)

            # D. Verify Invalid JWT throws InvalidBearerTokenException
            req_bad_jwt = build_mock_request({"Authorization": "Bearer this-is-a-bad-jwt-string"})
            with pytest.raises(InvalidBearerTokenException):
                await get_current_user(req_bad_jwt, session)

            # E. Verify Expired JWT throws TokenExpiredException
            expired_token = tokens.create_access_token(
                subject=str(created_user.id), expires_delta=timedelta(seconds=-10)
            )
            req_expired = build_mock_request({"Authorization": f"Bearer {expired_token}"})
            with pytest.raises(TokenExpiredException):
                await get_current_user(req_expired, session)

            # F. Verify Unknown User ID throws UserNotFoundException
            unknown_token = tokens.create_access_token(subject=str(uuid.uuid4()))
            req_unknown = build_mock_request({"Authorization": f"Bearer {unknown_token}"})
            with pytest.raises(UserNotFoundException):
                await get_current_user(req_unknown, session)

            # G. Verify Inactive User status throws InactiveAccountException
            await user_repo.deactivate_user(created_user.id)
            await session.commit()
            user = await get_current_user(req, session)
            with pytest.raises(InactiveAccountException):
                await get_current_active_user(user)

            # Reactivate for subsequent tests
            await user_repo.activate_user(created_user.id)
            await session.commit()

            # H. Verify Soft Deleted User status throws UserNotFoundException
            await user_repo.soft_delete_user(created_user.id)
            await session.commit()
            user = await get_current_user(req, session)
            with pytest.raises(UserNotFoundException):
                await get_current_active_user(user)

            # Restore user for subsequent tests
            await user_repo.restore_user(created_user.id)
            await session.commit()

            # I. Verify Inactive School tenant throws InactiveSchoolException
            school.is_active = False
            session.add(school)
            await session.commit()
            try:
                user = await get_current_user(req, session)
                with pytest.raises(InactiveSchoolException):
                    await get_current_active_user(user)
            finally:
                school.is_active = True
                session.add(school)
                await session.commit()

            # J. Verify Optional Authentication flows
            # Valid token resolves the user
            opt_user = await get_optional_current_user(req, session)
            assert opt_user is not None
            assert opt_user.id == created_user.id

            # Missing token resolves to None
            opt_anon = await get_optional_current_user(req_missing, session)
            assert opt_anon is None

            # Invalid token resolves to None
            opt_bad = await get_optional_current_user(req_bad_jwt, session)
            assert opt_bad is None

        finally:
            # Cleanup user record
            repo_user = UserRepository(session)
            db_user = await repo_user.get_by_id(created_user.id)
            if db_user:
                await repo_user.delete(db_user)
                await session.commit()
