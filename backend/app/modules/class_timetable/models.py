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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.class_timetable.enums import LessonType, TimetableStatus


class ClassTimetable(BaseEntity):
    """
    SQLAlchemy Model representing the overall timetable schedule configuration for a specific class section.
    """

    __tablename__ = "class_timetables"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[TimetableStatus] = mapped_column(
        Enum(TimetableStatus, name="timetable_status"),
        default=TimetableStatus.DRAFT,
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
    academic_year = relationship("AcademicYear")
    term = relationship("Term")
    school_class = relationship("SchoolClass", foreign_keys=[class_id])
    section = relationship("Section")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    entries = relationship(
        "ClassTimetableEntry",
        back_populates="timetable",
        cascade="all, delete-orphan",
    )


class ClassTimetableEntry(BaseEntity):
    """
    SQLAlchemy Model representing a single allocated period within a Class Timetable.
    """

    __tablename__ = "class_timetable_entries"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timetable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_timetables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    working_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_subject_allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teacher_subject_allocations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_type: Mapped[LessonType] = mapped_column(
        Enum(LessonType, name="class_timetable_lesson_type"),
        default=LessonType.THEORY,
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school = relationship("School")
    timetable = relationship("ClassTimetable", back_populates="entries")
    working_day = relationship("WorkingDay")
    time_slot = relationship("TimeSlot")
    teacher_subject_allocation = relationship("TeacherSubjectAllocation")
    teacher = relationship("Teacher")
    subject = relationship("Subject")
    room = relationship("Room")


class RecurringSchedule(BaseEntity):
    """
    SQLAlchemy Model representing the recurring rules associated with Class Timetables.
    """

    __tablename__ = "recurring_schedules"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timetable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_timetables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    recurrence_pattern: Mapped[str] = mapped_column(
        String(50), default="WEEKLY", nullable=False
    )

    # Relationships
    school = relationship("School")
    timetable = relationship("ClassTimetable")


# Indexes and unique constraints
Index(
    "ix_uq_school_class_timetable_version",
    ClassTimetable.school_id,
    ClassTimetable.class_id,
    ClassTimetable.section_id,
    ClassTimetable.academic_year_id,
    ClassTimetable.term_id,
    ClassTimetable.version,
    unique=True,
    postgresql_where=ClassTimetable.is_deleted == False,
)

Index(
    "ix_uq_timetable_entry_slot",
    ClassTimetableEntry.timetable_id,
    ClassTimetableEntry.working_day_id,
    ClassTimetableEntry.time_slot_id,
    unique=True,
    postgresql_where=ClassTimetableEntry.is_deleted == False,
)
