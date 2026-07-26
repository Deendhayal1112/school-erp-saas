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
from app.modules.designation.enums import DesignationStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.department.models import Department


class Designation(BaseEntity):
    """
    Designation ORM model representing job titles/roles mapped under Departments.
    """

    __tablename__ = "designations"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "designation_code", name="uq_designation_school_code"
        ),
        UniqueConstraint(
            "department_id", "designation_name", name="uq_designation_dept_name"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    designation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    designation_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    employment_category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Teaching, Admin, etc.
    job_level: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Entry, Mid, Senior, Executive
    grade: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Grade A, Grade B, etc.
    salary_band: Mapped[str | None] = mapped_column(String(100), nullable=True)

    minimum_salary: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.0, nullable=False
    )
    maximum_salary: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.0, nullable=False
    )

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[DesignationStatus] = mapped_column(
        Enum(DesignationStatus), default=DesignationStatus.ACTIVE, nullable=False
    )

    is_teaching: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_management: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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

    # Relationships
    school: Mapped["School"] = relationship("School")
    department: Mapped["Department"] = relationship("Department")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
