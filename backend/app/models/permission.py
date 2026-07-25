from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseEntity


class Permission(BaseEntity):
    """
    Permission Entity defining fine-grained action scopes (e.g., 'user.create', 'student.view')
    within the School ERP SaaS system.
    """
    __tablename__ = "permissions"

    # Core permission metadata
    name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Scoping categorization (e.g. 'users', 'students', 'billing')
    module: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # System flag to lock crucial platform permissions from deletion/modification
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
