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
from app.modules.academic_settings.enums import AcademicSettingsStatus

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.academic_year.models import AcademicYear
    from app.modules.term.models import Term


class AcademicSettings(BaseEntity):
    """
    AcademicSettings ORM model representing configuration variables and policies for a school's academic operations.
    """

    __tablename__ = "academic_settings"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "academic_year_id", name="uq_academic_settings_school_year"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    default_term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    default_language: Mapped[str] = mapped_column(
        String(50), default="English", nullable=False
    )
    grading_system: Mapped[str] = mapped_column(
        String(50), default="GPA", nullable=False
    )
    attendance_calculation_method: Mapped[str] = mapped_column(
        String(50), default="DAILY", nullable=False
    )
    promotion_policy: Mapped[str | None] = mapped_column(Text, nullable=True)

    passing_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), default=40.0, nullable=False
    )
    minimum_attendance_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), default=75.0, nullable=False
    )

    maximum_subjects_per_day: Mapped[int] = mapped_column(
        Integer, default=6, nullable=False
    )
    maximum_periods_per_day: Mapped[int] = mapped_column(
        Integer, default=8, nullable=False
    )
    working_days_per_week: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )

    academic_timezone: Mapped[str] = mapped_column(
        String(50), default="UTC", nullable=False
    )
    academic_calendar_type: Mapped[str] = mapped_column(
        String(50), default="SEMESTER", nullable=False
    )
    week_start_day: Mapped[str] = mapped_column(
        String(20), default="MONDAY", nullable=False
    )

    allow_subject_electives: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    allow_cross_section_subjects: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    allow_student_transfers: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    allow_mid_year_admission: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    auto_generate_roll_numbers: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    roll_number_prefix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roll_number_padding: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    default_class_capacity: Mapped[int] = mapped_column(
        Integer, default=40, nullable=False
    )

    status: Mapped[AcademicSettingsStatus] = mapped_column(
        Enum(AcademicSettingsStatus),
        default=AcademicSettingsStatus.ACTIVE,
        nullable=False,
    )
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
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear")
    default_term: Mapped["Term"] = relationship("Term")

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
