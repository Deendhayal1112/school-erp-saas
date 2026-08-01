"""
ORM Models for Timetable Adjustments & Teacher Substitution.

Models:
- TimetableAdjustment: A proposed change to a ClassTimetableEntry
- TeacherSubstitution: A temporary teacher replacement record
- AdjustmentHistory: Immutable history snapshots of each adjustment state change
- SubstitutionHistory: Immutable history snapshots of each substitution state change
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.timetable_adjustment.enums import (
    AdjustmentStatus,
    AdjustmentType,
    SubstitutionStatus,
    SubstitutionType,
)


class TimetableAdjustment(BaseEntity):
    """
    Represents a proposed or applied change to a single ClassTimetableEntry.

    Supports workflow: PENDING → APPROVED → APPLIED (or REJECTED / ROLLED_BACK).
    Tracks both the original and replacement values for full audit traceability.
    """

    __tablename__ = "timetable_adjustments"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_timetable_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_timetable_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adjustment_type: Mapped[AdjustmentType] = mapped_column(
        Enum(AdjustmentType, name="timetable_adjustment_type"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Original values (captured at creation time) ---
    old_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    old_room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )
    old_time_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("time_slots.id", ondelete="SET NULL"), nullable=True
    )
    old_working_day_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("working_days.id", ondelete="SET NULL"), nullable=True
    )

    # --- Proposed new values ---
    new_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    new_room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )
    new_time_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("time_slots.id", ondelete="SET NULL"), nullable=True
    )
    new_working_day_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("working_days.id", ondelete="SET NULL"), nullable=True
    )

    # --- Scheduling metadata ---
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Workflow ---
    status: Mapped[AdjustmentStatus] = mapped_column(
        Enum(AdjustmentStatus, name="timetable_adjustment_status"),
        default=AdjustmentStatus.PENDING,
        nullable=False,
        index=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Audit ---
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Relationships ---
    school = relationship("School")
    timetable_entry = relationship("ClassTimetableEntry")
    old_teacher = relationship("Teacher", foreign_keys=[old_teacher_id])
    new_teacher = relationship("Teacher", foreign_keys=[new_teacher_id])
    old_room = relationship("Room", foreign_keys=[old_room_id])
    new_room = relationship("Room", foreign_keys=[new_room_id])
    old_time_slot = relationship("TimeSlot", foreign_keys=[old_time_slot_id])
    new_time_slot = relationship("TimeSlot", foreign_keys=[new_time_slot_id])
    old_working_day = relationship("WorkingDay", foreign_keys=[old_working_day_id])
    new_working_day = relationship("WorkingDay", foreign_keys=[new_working_day_id])
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    history = relationship(
        "AdjustmentHistory",
        back_populates="adjustment",
        cascade="all, delete-orphan",
        order_by="AdjustmentHistory.changed_at",
    )


class TeacherSubstitution(BaseEntity):
    """
    Represents a temporary teacher substitution for a specific class period.

    Supports workflow: PENDING → APPROVED → ACTIVE → COMPLETED (or REJECTED / CANCELLED).
    """

    __tablename__ = "teacher_substitutions"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    substitute_teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
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
    working_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    substitution_type: Mapped[SubstitutionType] = mapped_column(
        Enum(SubstitutionType, name="teacher_substitution_type"),
        default=SubstitutionType.PLANNED,
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Workflow ---
    status: Mapped[SubstitutionStatus] = mapped_column(
        Enum(SubstitutionStatus, name="teacher_substitution_status"),
        default=SubstitutionStatus.PENDING,
        nullable=False,
        index=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    school = relationship("School")
    original_teacher = relationship("Teacher", foreign_keys=[original_teacher_id])
    substitute_teacher = relationship("Teacher", foreign_keys=[substitute_teacher_id])
    school_class = relationship("SchoolClass")
    section = relationship("Section")
    subject = relationship("Subject")
    working_day = relationship("WorkingDay")
    time_slot = relationship("TimeSlot")
    approver = relationship("User", foreign_keys=[approved_by])

    history = relationship(
        "SubstitutionHistory",
        back_populates="substitution",
        cascade="all, delete-orphan",
        order_by="SubstitutionHistory.changed_at",
    )


class AdjustmentHistory(BaseEntity):
    """
    Immutable audit snapshot capturing each state transition of a TimetableAdjustment.
    """

    __tablename__ = "adjustment_histories"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    adjustment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("timetable_adjustments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # --- Relationships ---
    school = relationship("School")
    adjustment = relationship("TimetableAdjustment", back_populates="history")
    actor = relationship("User")


class SubstitutionHistory(BaseEntity):
    """
    Immutable audit snapshot capturing each state transition of a TeacherSubstitution.
    """

    __tablename__ = "substitution_histories"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    substitution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_substitutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # --- Relationships ---
    school = relationship("School")
    substitution = relationship("TeacherSubstitution", back_populates="history")
    actor = relationship("User")


# Composite indexes for performance
Index(
    "ix_timetable_adjustment_school_status",
    TimetableAdjustment.school_id,
    TimetableAdjustment.status,
)
Index(
    "ix_timetable_adjustment_entry",
    TimetableAdjustment.class_timetable_entry_id,
    TimetableAdjustment.status,
)
Index(
    "ix_teacher_substitution_school_status",
    TeacherSubstitution.school_id,
    TeacherSubstitution.status,
)
Index(
    "ix_teacher_substitution_slot",
    TeacherSubstitution.substitute_teacher_id,
    TeacherSubstitution.working_day_id,
    TeacherSubstitution.time_slot_id,
)
