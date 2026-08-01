import uuid
from datetime import time

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.time_slot.enums import BreakType, SlotType


class TimeSlot(BaseEntity):
    """
    SQLAlchemy Model representing configured class schedule timing blocks per working day.
    """

    __tablename__ = "time_slots"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_type: Mapped[SlotType] = mapped_column(
        Enum(SlotType, name="timeslot_slot_type"),
        default=SlotType.TEACHING,
        nullable=False,
    )
    working_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_break: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_teaching: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    working_day = relationship("WorkingDay")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class Period(BaseEntity):
    """
    SQLAlchemy Model representing the link between a Time Slot and a Class Level (SchoolClass).
    """

    __tablename__ = "periods"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    default_subject_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=45, nullable=False
    )
    default_teacher_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=45, nullable=False
    )
    max_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    school = relationship("School")
    time_slot = relationship("TimeSlot")
    school_class = relationship("SchoolClass")


class BreakPeriod(BaseEntity):
    """
    SQLAlchemy Model representing recess, lunch, or prayer breaks associated with Time Slots.
    """

    __tablename__ = "break_periods"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    break_type: Mapped[BreakType] = mapped_column(
        Enum(BreakType, name="break_period_type"),
        default=BreakType.SHORT_BREAK,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    school = relationship("School")
    time_slot = relationship("TimeSlot")


# Unique Constraints and Indexes
Index(
    "ix_uq_school_wd_display_order",
    TimeSlot.school_id,
    TimeSlot.working_day_id,
    TimeSlot.display_order,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_wd_slot_number",
    TimeSlot.school_id,
    TimeSlot.working_day_id,
    TimeSlot.slot_number,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_ts_class",
    Period.school_id,
    Period.time_slot_id,
    Period.class_id,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_ts_break",
    BreakPeriod.school_id,
    BreakPeriod.time_slot_id,
    BreakPeriod.name,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
