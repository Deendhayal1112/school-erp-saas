import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.exceptions import DuplicateEntityError
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_user_repository_flows():
    """
    Integration test verifying complete UserRepository and BaseRepository CRUD execution,
    eager query loading, soft delete/restore parameters, and constraint error translations.
    """
    async with AsyncSessionLocal() as session:
        # 1. Fetch seeded dependencies (school and role)
        school_stmt = select(School).limit(1)
        school_res = await session.execute(school_stmt)
        school = school_res.scalar_one_or_none()
        assert school is not None, "Ensure database is seeded with a School record before running tests"

        role_stmt = select(Role).where(Role.code == "TEACHER")
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        assert role is not None, "Ensure database is seeded with a TEACHER Role record before running tests"

        repo = UserRepository(session)

        # Define test unique variables
        test_email = f"repo_test_{uuid.uuid4().hex[:8]}@demoschool.edu"
        test_username = f"repotest_{uuid.uuid4().hex[:8]}"

        # Assert exists check returns False on non-existent records
        assert await repo.exists_by_email(test_email) is False
        assert await repo.exists_by_username(test_username) is False

        # 2. Verify Create User flow
        test_user = User(
            first_name="Repository",
            last_name="Tester",
            username=test_username,
            email=test_email,
            password_hash="dummy_bcrypt_hash_placeholder",
            school_id=school.id,
            role_id=role.id,
            status="active",
        )
        created_user = await repo.create_user(test_user)
        await session.commit()

        try:
            assert created_user.id is not None
            assert created_user.email == test_email

            # 3. Verify Get by ID (includes eager loaded relations)
            user_by_id = await repo.get_by_id(created_user.id)
            assert user_by_id is not None
            assert user_by_id.id == created_user.id
            assert user_by_id.school.name == school.name
            assert user_by_id.role.code == "TEACHER"

            # 4. Verify Get by Email
            user_by_email = await repo.get_by_email(test_email)
            assert user_by_email is not None
            assert user_by_email.id == created_user.id

            # 5. Verify Get by Username
            user_by_username = await repo.get_by_username(test_username)
            assert user_by_username is not None
            assert user_by_username.id == created_user.id

            # 6. Verify Exists checks
            assert await repo.exists_by_email(test_email) is True
            assert await repo.exists_by_username(test_username) is True

            # 7. Verify Update User details
            user_by_id.first_name = "ModifiedRepositoryName"
            updated_user = await repo.update_user(user_by_id)
            await session.commit()
            assert updated_user.first_name == "ModifiedRepositoryName"

            # 8. Verify Update Last Login
            login_time = datetime.now(UTC)
            await repo.update_last_login(created_user.id, login_time)
            await session.commit()

            refreshed_user = await repo.get_by_id(created_user.id)
            assert refreshed_user.last_login is not None

            # 9. Verify Deactivate and Activate flows
            await repo.deactivate_user(created_user.id)
            await session.commit()
            refreshed_user = await repo.get_by_id(created_user.id)
            assert refreshed_user.is_active is False
            assert refreshed_user.status == "inactive"

            await repo.activate_user(created_user.id)
            await session.commit()
            refreshed_user = await repo.get_by_id(created_user.id)
            assert refreshed_user.is_active is True
            assert refreshed_user.status == "active"

            # 10. Verify Soft Delete and Restore flows
            await repo.soft_delete_user(created_user.id)
            await session.commit()
            refreshed_user = await repo.get_by_id(created_user.id)
            assert refreshed_user.is_deleted is True
            assert refreshed_user.deleted_at is not None

            await repo.restore_user(created_user.id)
            await session.commit()
            refreshed_user = await repo.get_by_id(created_user.id)
            assert refreshed_user.is_deleted is False
            assert refreshed_user.deleted_at is None

            # 11. Verify Count
            current_count = await repo.count()
            assert current_count >= 1

            # 12. Verify Duplicate Email Constraint Handling
            duplicate_user = User(
                first_name="Duplicate",
                last_name="User",
                username=f"dup_{uuid.uuid4().hex[:8]}",
                email=test_email,  # Intentionally duplicated
                password_hash="dummy_hash",
                school_id=school.id,
                role_id=role.id,
            )
            with pytest.raises(DuplicateEntityError):
                await repo.create_user(duplicate_user)
                await session.commit()

        finally:
            # 13. Cleanup test records
            await repo.delete(created_user)
            await session.commit()
