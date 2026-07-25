import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.permission import Permission
    from app.models.role import Role


class RolePermission(BaseEntity):
    """
    Association Entity implementing the Many-to-Many junction between Roles and Permissions.
    Maps which permissions are granted to which roles.
    """

    __tablename__ = "role_permissions"

    # Foreign Keys referencing Role and Permission tables
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Table arguments enforcing uniqueness constraints
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    # ORM Relationships
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="role_permissions",
    )
    permission: Mapped["Permission"] = relationship(
        "Permission",
        back_populates="role_permissions",
    )
