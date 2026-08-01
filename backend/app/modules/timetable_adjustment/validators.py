"""
Business rule validators for Timetable Adjustments & Teacher Substitution.
"""

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.class_timetable.models import ClassTimetableEntry
from app.modules.room.models import Room
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import TeacherSubjectAllocation
from app.modules.teacher_timetable.enums import TeacherAvailabilityStatus
from app.modules.teacher_timetable.models import TeacherAvailability
from app.modules.timetable_adjustment.exceptions import (
    AdjustmentConflictException,
    InvalidEffectiveDateException,
    InvalidExpiryDateException,
    RoomNotAvailableException,
    TimetableEntryNotFoundException,
    TeacherNotAvailableException,
    TeacherNotQualifiedException,
    TeacherNotFoundException,
)
from app.modules.timetable_adjustment.schemas import TimetableAdjustmentCreate


async def validate_timetable_entry_exists(
    db: AsyncSession,
    entry_id: uuid.UUID,
    school_id: uuid.UUID,
) -> ClassTimetableEntry:
    """Ensure the referenced timetable entry exists and belongs to the school."""
    stmt = select(ClassTimetableEntry).where(
        ClassTimetableEntry.id == entry_id,
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.is_deleted == False,
    )
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if not entry:
        raise TimetableEntryNotFoundException()
    return entry


async def validate_teacher_exists(
    db: AsyncSession,
    teacher_id: uuid.UUID,
    school_id: uuid.UUID,
) -> Teacher:
    """Ensure teacher exists and belongs to the school."""
    stmt = select(Teacher).where(
        Teacher.id == teacher_id,
        Teacher.school_id == school_id,
        Teacher.is_deleted == False,
    )
    teacher = (await db.execute(stmt)).scalar_one_or_none()
    if not teacher:
        raise TeacherNotFoundException()
    return teacher


async def validate_teacher_qualified(
    db: AsyncSession,
    teacher_id: uuid.UUID,
    subject_id: uuid.UUID,
    school_id: uuid.UUID,
) -> None:
    """Ensure the substitute teacher has a subject allocation for this subject."""
    stmt = select(TeacherSubjectAllocation).where(
        TeacherSubjectAllocation.teacher_id == teacher_id,
        TeacherSubjectAllocation.subject_id == subject_id,
        TeacherSubjectAllocation.school_id == school_id,
        TeacherSubjectAllocation.is_deleted == False,
    )
    alloc = (await db.execute(stmt)).scalars().first()
    if not alloc:
        raise TeacherNotQualifiedException()


async def validate_teacher_available_at_slot(
    db: AsyncSession,
    teacher_id: uuid.UUID,
    working_day_id: uuid.UUID,
    time_slot_id: uuid.UUID,
    school_id: uuid.UUID,
    exclude_entry_id: uuid.UUID | None = None,
) -> None:
    """
    Ensure teacher is not already booked at the given slot (via timetable entries).
    Optionally exclude one entry (the one being adjusted).
    """
    stmt = select(ClassTimetableEntry).where(
        ClassTimetableEntry.teacher_id == teacher_id,
        ClassTimetableEntry.working_day_id == working_day_id,
        ClassTimetableEntry.time_slot_id == time_slot_id,
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.is_deleted == False,
    )
    if exclude_entry_id:
        stmt = stmt.where(ClassTimetableEntry.id != exclude_entry_id)

    conflict = (await db.execute(stmt)).scalars().first()
    if conflict:
        raise TeacherNotAvailableException(
            "Substitute teacher already has a class at this slot."
        )

    # Also check TeacherAvailability blocks
    avail_stmt = select(TeacherAvailability).where(
        TeacherAvailability.teacher_id == teacher_id,
        TeacherAvailability.working_day_id == working_day_id,
        TeacherAvailability.time_slot_id == time_slot_id,
        TeacherAvailability.school_id == school_id,
        TeacherAvailability.availability_status == TeacherAvailabilityStatus.UNAVAILABLE,
        TeacherAvailability.is_deleted == False,
    )
    blocked = (await db.execute(avail_stmt)).scalars().first()
    if blocked:
        raise TeacherNotAvailableException(
            "Teacher has marked themselves unavailable at this slot."
        )


async def validate_room_available(
    db: AsyncSession,
    room_id: uuid.UUID,
    working_day_id: uuid.UUID,
    time_slot_id: uuid.UUID,
    school_id: uuid.UUID,
    exclude_entry_id: uuid.UUID | None = None,
) -> None:
    """Ensure the room is not already booked at the target slot."""
    stmt = select(ClassTimetableEntry).where(
        ClassTimetableEntry.room_id == room_id,
        ClassTimetableEntry.working_day_id == working_day_id,
        ClassTimetableEntry.time_slot_id == time_slot_id,
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.is_deleted == False,
    )
    if exclude_entry_id:
        stmt = stmt.where(ClassTimetableEntry.id != exclude_entry_id)

    conflict = (await db.execute(stmt)).scalars().first()
    if conflict:
        raise RoomNotAvailableException()


def validate_effective_date(effective_date: datetime.date) -> None:
    """Effective date must be today or in the future."""
    if effective_date < datetime.date.today():
        raise InvalidEffectiveDateException()


def validate_expiry_date(effective_date: datetime.date, expiry_date: datetime.date | None) -> None:
    """Expiry date must be >= effective date."""
    if expiry_date is not None and expiry_date < effective_date:
        raise InvalidExpiryDateException()
