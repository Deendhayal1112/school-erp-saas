import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.department.enums import DepartmentStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User


class Department(BaseEntity):
    """
    Department ORM model representing an academic or administrative division in a School.
    """

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "department_code", name="uq_departments_school_code"
        ),
        UniqueConstraint(
            "school_id", "department_name", name="uq_departments_school_name"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_code: Mapped[str] = mapped_column(String(50), nullable=False)
    department_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    head_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)

    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    budget: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[DepartmentStatus] = mapped_column(
        Enum(DepartmentStatus), default=DepartmentStatus.ACTIVE, nullable=False
    )

    is_academic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Tenant Relationship
    school: Mapped["School"] = relationship("School")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
