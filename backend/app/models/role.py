from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseEntity


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
