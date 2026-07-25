import uuid
from datetime import UTC, datetime

from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.exceptions import EntityNotFoundError
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    User-specific Repository mapping complex database read/write queries.
    Utilizes joined/selectin loading options to optimize permission checks and avoid N+1 loads.
    """

    def __init__(self, session):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """
        Retrieves a user by email address.
        Loads associated School, Role, and RolePermissions -> Permissions collections eagerly.
        """
        stmt = (
            select(User)
            .where(User.email == email)
            .options(
                joinedload(User.school),
                joinedload(User.role)
                .selectinload(Role.role_permissions)
                .joinedload(RolePermission.permission),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, id: uuid.UUID) -> User | None:
        """
        Retrieves a user by ID.
        Loads associated School, Role, and RolePermissions -> Permissions collections eagerly.
        """
        stmt = (
            select(User)
            .where(User.id == id)
            .options(
                joinedload(User.school),
                joinedload(User.role)
                .selectinload(Role.role_permissions)
                .joinedload(RolePermission.permission),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """
        Retrieves a user by username.
        Loads associated School, Role, and RolePermissions -> Permissions collections eagerly.
        """
        stmt = (
            select(User)
            .where(User.username == username)
            .options(
                joinedload(User.school),
                joinedload(User.role)
                .selectinload(Role.role_permissions)
                .joinedload(RolePermission.permission),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        """Persists a new user record in the database."""
        return await self.create(user)

    async def update_user(self, user: User) -> User:
        """Updates an existing user record in the database."""
        return await self.update(user)

    async def update_last_login(self, user_id: uuid.UUID, last_login_dt: datetime) -> None:
        """Updates the last_login timestamp audit field of a user."""
        user = await super().get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")
        user.last_login = last_login_dt
        await self.update(user)

    async def activate_user(self, user_id: uuid.UUID) -> None:
        """Sets the user activation status to active."""
        user = await super().get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")
        user.status = "active"
        user.is_active = True
        await self.update(user)

    async def deactivate_user(self, user_id: uuid.UUID) -> None:
        """Sets the user activation status to inactive."""
        user = await super().get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")
        user.status = "inactive"
        user.is_active = False
        await self.update(user)

    async def soft_delete_user(self, user_id: uuid.UUID) -> None:
        """Soft deletes the user record by marking is_deleted=True."""
        user = await super().get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")
        user.is_deleted = True
        user.deleted_at = datetime.now(UTC)
        await self.update(user)

    async def restore_user(self, user_id: uuid.UUID) -> None:
        """Restores a soft-deleted user record by marking is_deleted=False."""
        user = await super().get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")
        user.is_deleted = False
        user.deleted_at = None
        await self.update(user)

    async def exists_by_email(self, email: str) -> bool:
        """Checks if a user email address exists in the database."""
        stmt = select(User.id).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_by_username(self, username: str) -> bool:
        """Checks if a username identifier exists in the database."""
        stmt = select(User.id).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
