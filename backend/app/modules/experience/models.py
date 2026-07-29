import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.experience.enums import (
    EmploymentType,
    ExperienceStatus,
    OrganizationType,
)

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.employee.models import Employee


class Experience(BaseEntity):
    """
    SQLAlchemy Model representing previous or current professional work experiences of an Employee.
    """

    __tablename__ = "experiences"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType), nullable=False
    )
    organization_name: Mapped[str] = mapped_column(String(150), nullable=False)
    organization_type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType), nullable=False
    )
    designation: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    employment_category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currently_working: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    experience_years: Mapped[int | None] = mapped_column(
        Integer, default=0, nullable=True
    )
    experience_months: Mapped[int | None] = mapped_column(
        Integer, default=0, nullable=True
    )

    salary: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(
        String(10), default="INR", nullable=True
    )

    reason_for_leaving: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    achievements: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_used: Mapped[str | None] = mapped_column(Text, nullable=True)

    manager_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    manager_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    manager_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_available: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    experience_certificate_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    verification_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExperienceStatus] = mapped_column(
        Enum(ExperienceStatus),
        default=ExperienceStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    employee: Mapped["Employee"] = relationship("Employee")
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], backref="created_experiences"
    )
    updater: Mapped["User"] = relationship(
        "User", foreign_keys=[updated_by], backref="updated_experiences"
    )
    verifier: Mapped["User"] = relationship(
        "User", foreign_keys=[verification_by], backref="verified_experiences"
    )
