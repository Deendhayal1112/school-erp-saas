import uuid

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.teacher_subject_allocation.enums import AllocationStatus


class TeacherSubjectAllocation(BaseEntity):
    """
    SQLAlchemy Model mapping a teacher to a specific subject, class, and section for a term.
    """

    __tablename__ = "teacher_subject_allocations"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weekly_period_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_periods: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preferred_room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )
    preferred_shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_shifts.id", ondelete="SET NULL"), nullable=True
    )
    is_class_teacher: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_primary_teacher: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[Date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AllocationStatus] = mapped_column(
        Enum(AllocationStatus, name="allocation_status"), default=AllocationStatus.ACTIVE, nullable=False
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school = relationship("School")
    teacher = relationship("Teacher")
    academic_year = relationship("AcademicYear")
    term = relationship("Term")
    school_class = relationship("SchoolClass")
    section = relationship("Section")
    subject = relationship("Subject")
    preferred_room = relationship("Room")
    preferred_shift = relationship("AttendanceShift")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class TeacherWorkload(BaseEntity):
    """
    SQLAlchemy Model defining standard workload capacities and constraints for a teacher.
    """

    __tablename__ = "teacher_workloads"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    maximum_weekly_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_periods: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remaining_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    consecutive_period_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    school = relationship("School")
    teacher = relationship("Teacher")


class SubjectQualification(BaseEntity):
    """
    SQLAlchemy Model mapping teacher qualification certifications and experience per subject.
    """

    __tablename__ = "subject_qualifications"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qualification_level: Mapped[str] = mapped_column(String(100), nullable=False)
    certified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    school = relationship("School")
    teacher = relationship("Teacher")
    subject = relationship("Subject")


# Unique Constraints and Indexes
Index(
    "ix_uq_school_teacher_allocation",
    TeacherSubjectAllocation.school_id,
    TeacherSubjectAllocation.teacher_id,
    TeacherSubjectAllocation.academic_year_id,
    TeacherSubjectAllocation.term_id,
    TeacherSubjectAllocation.class_id,
    TeacherSubjectAllocation.section_id,
    TeacherSubjectAllocation.subject_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_teacher_workload",
    TeacherWorkload.school_id,
    TeacherWorkload.teacher_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_subject_qualification",
    SubjectQualification.school_id,
    SubjectQualification.teacher_id,
    SubjectQualification.subject_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
