import uuid
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseEntity


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
