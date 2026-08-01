"""
Adjustment Engine: validates proposed timetable changes for conflicts
before committing them to the database.
"""

import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.class_timetable.models import ClassTimetableEntry
from app.modules.timetable_adjustment.enums import AdjustmentType
from app.modules.timetable_adjustment.exceptions import (
    AdjustmentConflictException,
    RoomNotAvailableException,
    TeacherNotAvailableException,
)
from app.modules.timetable_adjustment.models import TimetableAdjustment

logger = logging.getLogger(__name__)


class AdjustmentEngine:
    """
    Validates proposed changes against live timetable state.
    Run before persisting any adjustment to guard against conflicts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def validate_adjustment(
        self,
        adjustment: TimetableAdjustment,
        entry: ClassTimetableEntry,
    ) -> None:
        """
        Runs the full conflict-check suite for a given adjustment proposal.
        Raises specific exceptions describing violations.
        """
        adj_type = adjustment.adjustment_type

        if adj_type == AdjustmentType.TEACHER_CHANGE and adjustment.new_teacher_id:
            await self._check_teacher_slot_free(
                teacher_id=adjustment.new_teacher_id,
                working_day_id=entry.working_day_id,
                time_slot_id=entry.time_slot_id,
                school_id=adjustment.school_id,
                exclude_entry_id=entry.id,
            )

        elif adj_type == AdjustmentType.ROOM_CHANGE and adjustment.new_room_id:
            await self._check_room_slot_free(
                room_id=adjustment.new_room_id,
                working_day_id=entry.working_day_id,
                time_slot_id=entry.time_slot_id,
                school_id=adjustment.school_id,
                exclude_entry_id=entry.id,
            )

        elif adj_type == AdjustmentType.TIME_SLOT_CHANGE and adjustment.new_time_slot_id:
            await self._check_teacher_slot_free(
                teacher_id=entry.teacher_id,
                working_day_id=entry.working_day_id,
                time_slot_id=adjustment.new_time_slot_id,
                school_id=adjustment.school_id,
                exclude_entry_id=entry.id,
            )
            if entry.room_id:
                await self._check_room_slot_free(
                    room_id=entry.room_id,
                    working_day_id=entry.working_day_id,
                    time_slot_id=adjustment.new_time_slot_id,
                    school_id=adjustment.school_id,
                    exclude_entry_id=entry.id,
                )

        elif adj_type == AdjustmentType.WORKING_DAY_CHANGE and adjustment.new_working_day_id:
            await self._check_teacher_slot_free(
                teacher_id=entry.teacher_id,
                working_day_id=adjustment.new_working_day_id,
                time_slot_id=entry.time_slot_id,
                school_id=adjustment.school_id,
                exclude_entry_id=entry.id,
            )

        elif adj_type == AdjustmentType.EMERGENCY_ADJUSTMENT:
            # Emergency: validate both teacher and room if new values provided
            if adjustment.new_teacher_id:
                await self._check_teacher_slot_free(
                    teacher_id=adjustment.new_teacher_id,
                    working_day_id=adjustment.new_working_day_id or entry.working_day_id,
                    time_slot_id=adjustment.new_time_slot_id or entry.time_slot_id,
                    school_id=adjustment.school_id,
                    exclude_entry_id=entry.id,
                )
            if adjustment.new_room_id:
                await self._check_room_slot_free(
                    room_id=adjustment.new_room_id,
                    working_day_id=adjustment.new_working_day_id or entry.working_day_id,
                    time_slot_id=adjustment.new_time_slot_id or entry.time_slot_id,
                    school_id=adjustment.school_id,
                    exclude_entry_id=entry.id,
                )

        logger.debug(
            "Adjustment validation passed: type=%s entry=%s",
            adj_type, entry.id,
        )

    async def apply_adjustment(
        self,
        adjustment: TimetableAdjustment,
        entry: ClassTimetableEntry,
    ) -> ClassTimetableEntry:
        """
        Applies the approved adjustment's new values onto the live timetable entry.
        Returns the mutated (but not yet committed) entry.
        """
        if adjustment.new_teacher_id:
            entry.teacher_id = adjustment.new_teacher_id
        if adjustment.new_room_id:
            entry.room_id = adjustment.new_room_id
        if adjustment.new_time_slot_id:
            entry.time_slot_id = adjustment.new_time_slot_id
        if adjustment.new_working_day_id:
            entry.working_day_id = adjustment.new_working_day_id

        self.db.add(entry)
        return entry

    async def rollback_adjustment(
        self,
        adjustment: TimetableAdjustment,
        entry: ClassTimetableEntry,
    ) -> ClassTimetableEntry:
        """
        Rolls back a previously APPLIED adjustment to restore original values.
        """
        if adjustment.old_teacher_id is not None:
            entry.teacher_id = adjustment.old_teacher_id
        if adjustment.old_room_id is not None:
            entry.room_id = adjustment.old_room_id
        if adjustment.old_time_slot_id is not None:
            entry.time_slot_id = adjustment.old_time_slot_id
        if adjustment.old_working_day_id is not None:
            entry.working_day_id = adjustment.old_working_day_id

        self.db.add(entry)
        return entry

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _check_teacher_slot_free(
        self,
        teacher_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        school_id: uuid.UUID,
        exclude_entry_id: uuid.UUID,
    ) -> None:
        stmt = select(ClassTimetableEntry).where(
            ClassTimetableEntry.teacher_id == teacher_id,
            ClassTimetableEntry.working_day_id == working_day_id,
            ClassTimetableEntry.time_slot_id == time_slot_id,
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.id != exclude_entry_id,
            ClassTimetableEntry.is_deleted == False,
        )
        conflict = (await self.db.execute(stmt)).scalars().first()
        if conflict:
            raise AdjustmentConflictException(
                "Teacher is already assigned to another class at this slot."
            )

    async def _check_room_slot_free(
        self,
        room_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        school_id: uuid.UUID,
        exclude_entry_id: uuid.UUID,
    ) -> None:
        stmt = select(ClassTimetableEntry).where(
            ClassTimetableEntry.room_id == room_id,
            ClassTimetableEntry.working_day_id == working_day_id,
            ClassTimetableEntry.time_slot_id == time_slot_id,
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.id != exclude_entry_id,
            ClassTimetableEntry.is_deleted == False,
        )
        conflict = (await self.db.execute(stmt)).scalars().first()
        if conflict:
            raise AdjustmentConflictException(
                "Room is already booked for another class at this slot."
            )
