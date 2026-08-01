import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.class_timetable.enums import LessonType
from app.modules.teacher_timetable.enums import (
    TeacherAvailabilityStatus,
    TeacherTimetableStatus,
)


class TeacherTimetable(BaseEntity):
    """
    SQLAlchemy Model representing the schedule version for a specific teacher.
    """

    __tablename__ = "teacher_timetables"

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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[TeacherTimetableStatus] = mapped_column(
        Enum(TeacherTimetableStatus, name="teacher_timetable_status"),
        default=TeacherTimetableStatus.DRAFT,
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    entries = relationship(
        "TeacherTimetableEntry",
        back_populates="timetable",
        cascade="all, delete-orphan",
    )


class TeacherTimetableEntry(BaseEntity):
    """
    SQLAlchemy Model representing a single scheduled period in a teacher's schedule.
    """

    __tablename__ = "teacher_timetable_entries"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_timetable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_timetables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    working_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_timetable_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_timetable_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lesson_type: Mapped[LessonType] = mapped_column(
        Enum(LessonType, name="teacher_timetable_lesson_type"),
        default=LessonType.THEORY,
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school = relationship("School")
    timetable = relationship("TeacherTimetable", back_populates="entries")
    working_day = relationship("WorkingDay")
    time_slot = relationship("TimeSlot")
    class_timetable_entry = relationship("ClassTimetableEntry")
    school_class = relationship("SchoolClass")
    section = relationship("Section")
    subject = relationship("Subject")
    room = relationship("Room")


class TeacherAvailability(BaseEntity):
    """
    SQLAlchemy Model representing custom teacher availability/unavailability blocks.
    """

    __tablename__ = "teacher_availabilities"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    working_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    availability_status: Mapped[TeacherAvailabilityStatus] = mapped_column(
        Enum(TeacherAvailabilityStatus, name="teacher_availability_status"),
        default=TeacherAvailabilityStatus.AVAILABLE,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    school = relationship("School")
    teacher = relationship("Teacher")
    working_day = relationship("WorkingDay")
    time_slot = relationship("TimeSlot")


# Unique constraints and indexes to prevent overlaps and ensure data integrity
Index(
    "ix_uq_teacher_timetable_version",
    TeacherTimetable.school_id,
    TeacherTimetable.teacher_id,
    TeacherTimetable.academic_year_id,
    TeacherTimetable.term_id,
    TeacherTimetable.version,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)

Index(
    "ix_uq_teacher_timetable_entry_slot",
    TeacherTimetableEntry.school_id,
    TeacherTimetableEntry.teacher_timetable_id,
    TeacherTimetableEntry.working_day_id,
    TeacherTimetableEntry.time_slot_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)

Index(
    "ix_uq_teacher_availability_slot",
    TeacherAvailability.school_id,
    TeacherAvailability.teacher_id,
    TeacherAvailability.working_day_id,
    TeacherAvailability.time_slot_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
