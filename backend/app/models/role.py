from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.role_permission import RolePermission


class Role(BaseEntity):
    """
    Role Entity defining authorization roles for users in the School ERP SaaS system.
    Determines user scopes and system access levels (e.g. Super Admin, Principal, Teacher).
    """
    __tablename__ = "roles"

    # Core metadata
    name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # System flag to prevent modification or deletion of crucial system roles
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ORM Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="role",
    )
    role_permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
