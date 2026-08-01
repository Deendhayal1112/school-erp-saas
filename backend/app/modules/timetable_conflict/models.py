import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.timetable_conflict.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
)


class ConflictRecord(BaseEntity):
    """
    SQLAlchemy Model representing a detected timetable conflict.
    """

    __tablename__ = "conflict_records"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conflict_type: Mapped[ConflictType] = mapped_column(
        Enum(ConflictType, name="timetable_conflict_type"), nullable=False
    )
    severity: Mapped[ConflictSeverity] = mapped_column(
        Enum(ConflictSeverity, name="timetable_conflict_severity"), nullable=False
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    working_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ConflictStatus] = mapped_column(
        Enum(ConflictStatus, name="timetable_conflict_status"),
        default=ConflictStatus.PENDING,
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school = relationship("School")
    generation_job = relationship("GenerationJob")
    school_class = relationship("SchoolClass")
    section = relationship("Section")
    teacher = relationship("Teacher")
    room = relationship("Room")
    subject = relationship("Subject")
    working_day = relationship("WorkingDay")
    time_slot = relationship("TimeSlot")
    resolver = relationship("User")

    resolutions = relationship("ConflictResolution", back_populates="conflict", cascade="all, delete-orphan")
    logs = relationship("ConflictLog", back_populates="conflict", cascade="all, delete-orphan")


class ConflictResolution(BaseEntity):
    """
    SQLAlchemy Model representing details of a conflict resolution.
    """

    __tablename__ = "conflict_resolutions"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conflict_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conflict_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resolution_strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    school = relationship("School")
    conflict = relationship("ConflictRecord", back_populates="resolutions")
    user = relationship("User")


class ConflictLog(BaseEntity):
    """
    SQLAlchemy Model representing execution logs/actions performed for conflicts.
    """

    __tablename__ = "conflict_logs"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conflict_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conflict_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    school = relationship("School")
    conflict = relationship("ConflictRecord", back_populates="logs")
