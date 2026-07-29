import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.teacher.enums import EmploymentMode, TeacherType

if TYPE_CHECKING:
    from app.models.school import School
    from app.modules.academic_year.models import AcademicYear
    from app.modules.department.models import Department
    from app.modules.employee.models import Employee


class Teacher(BaseEntity):
    """
    Teacher profile database table holding teacher information,
    preferences, limits, and relationships to academic settings.
    """

    __tablename__ = "teachers"

    __table_args__ = (
        UniqueConstraint("school_id", "teacher_code", name="uq_teachers_school_code"),
        UniqueConstraint(
            "school_id", "official_email", name="uq_teachers_school_email"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    teacher_code: Mapped[str] = mapped_column(String(50), nullable=False)
    teacher_type: Mapped[TeacherType] = mapped_column(
        Enum(TeacherType, name="teachertype"), nullable=False
    )
    employment_mode: Mapped[EmploymentMode] = mapped_column(
        Enum(EmploymentMode, name="employmentmode"), nullable=False
    )
    joining_academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    staff_room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    official_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extension_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    office_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    teaching_experience_years: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    highest_qualification: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
    specialization: Mapped[str | None] = mapped_column(String(150), nullable=True)
    subject_preferences: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    class_teacher_preference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    max_teaching_hours_per_week: Mapped[int] = mapped_column(
        Integer, default=40, nullable=False
    )
    is_class_teacher: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_subject_teacher: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    is_exam_evaluator: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    employee: Mapped["Employee"] = relationship(
        "Employee", back_populates="teacher_profile", lazy="raise"
    )
    department: Mapped["Department"] = relationship("Department", lazy="raise")
    joining_academic_year: Mapped["AcademicYear | None"] = relationship(
        "AcademicYear", lazy="raise"
    )
