import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseEntity
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.role import Role


class User(BaseEntity):
    """
    User Entity representing registration profiles (Admins, Staff, Students, Parents)
    registered under a School tenant in the School ERP SaaS system.
    """
    __tablename__ = "users"

    # ==========================================
    # Identity Fields
    # ==========================================
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ==========================================
    # Authentication Fields
    # ==========================================
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ==========================================
    # Profile Fields
    # ==========================================
    profile_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ==========================================
    # Status Fields
    # ==========================================
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ==========================================
    # Foreign Key Constraints
    # ==========================================
    # Cascade user deletion if a School tenant is removed
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Restrict role deletion if users are currently assigned that role
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ORM Relationships
    school: Mapped["School"] = relationship(
        "School",
        back_populates="users",
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="users",
    )
