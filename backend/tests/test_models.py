import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.role import Role


@pytest.mark.asyncio
async def test_create_and_read_role():
    """
    Integration test verifying that the database engine, session factory,
    and Role entity successfully execute write, read, and delete transactions
    against the live PostgreSQL database.
    """
    async with AsyncSessionLocal() as session:
        # 1. Create a test Role instance
        test_role = Role(
            name="QA Test Administrator",
            code="QA_TEST_ADMIN",
            description="Temporary role used to verify model constraints during testing",
            is_system=False,
        )
        session.add(test_role)
        await session.commit()

        try:
            # 2. Query the role back from the database
            stmt = select(Role).where(Role.code == "QA_TEST_ADMIN")
            result = await session.execute(stmt)
            queried_role = result.scalar_one_or_none()

            # 3. Assert mapping and database defaults work correctly
            assert queried_role is not None
            assert queried_role.name == "QA Test Administrator"
            assert queried_role.code == "QA_TEST_ADMIN"
            assert queried_role.is_system is False
            assert queried_role.is_active is True  # Default from BaseEntity
            assert queried_role.is_deleted is False  # Default from BaseEntity
            assert queried_role.created_at is not None  # Server-default timestamp
            assert queried_role.updated_at is not None  # Server-default timestamp

        finally:
            # 4. Clean up the database state by deleting the test record
            if queried_role:
                await session.delete(queried_role)
                await session.commit()
