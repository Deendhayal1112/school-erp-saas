import datetime
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.academic_calendar.models import WorkingDay
from app.modules.class_timetable.models import ClassTimetableEntry
from app.modules.room.models import Room
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
)
from app.modules.time_slot.models import TimeSlot
from app.modules.timetable_conflict.enums import ConflictStatus
from app.modules.timetable_conflict.exceptions import ResolutionFailedException
from app.modules.timetable_conflict.models import ConflictRecord, ConflictResolution
from app.modules.timetable_conflict.schemas import AlternativeSuggestion

logger = logging.getLogger(__name__)


class TimetableResolutionEngine:
    """
    Resolution search engine proposing and executing changes (swapping rooms,
    reassigning teachers, shifting slots) to resolve active timetable conflicts.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def suggest_alternatives(
        self, conflict: ConflictRecord
    ) -> list[AlternativeSuggestion]:
        """
        Scans database parameters to find free and valid alternative teachers, rooms, and slots.
        """
        suggestions: list[AlternativeSuggestion] = []
        school_id = conflict.school_id
        wd_id = conflict.working_day_id
        ts_id = conflict.time_slot_id
        subject_id = conflict.subject_id

        # 1. Propose Alternative Teachers
        # Find teachers allocated/qualified for this subject who are not teaching at this slot
        alloc_stmt = select(TeacherSubjectAllocation).where(
            TeacherSubjectAllocation.school_id == school_id,
            TeacherSubjectAllocation.subject_id == subject_id,
            TeacherSubjectAllocation.is_deleted == False,
        )
        allocs = (await self.session.execute(alloc_stmt)).scalars().all()
        qualified_teacher_ids = {al.teacher_id for al in allocs if al.teacher_id != conflict.teacher_id}

        for t_id in qualified_teacher_ids:
            # Check if teacher is double booked at this slot
            booked_stmt = select(ClassTimetableEntry).where(
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.teacher_id == t_id,
                ClassTimetableEntry.working_day_id == wd_id,
                ClassTimetableEntry.time_slot_id == ts_id,
                ClassTimetableEntry.is_deleted == False,
            )
            booked = (await self.session.execute(booked_stmt)).scalars().all()
            if not booked:
                # Fetch teacher code/name
                t_stmt = select(Teacher).options(joinedload(Teacher.employee)).where(Teacher.id == t_id)
                t_obj = (await self.session.execute(t_stmt)).scalar_one_or_none()
                t_name = f"{t_obj.employee.first_name} {t_obj.employee.last_name}" if t_obj and t_obj.employee else "Teacher"
                suggestions.append(
                    AlternativeSuggestion(
                        teacher_id=t_id,
                        teacher_name=t_name,
                    )
                )

        # 2. Propose Alternative Rooms
        # Find rooms that are empty at this slot and have enough capacity
        room_stmt = select(Room).where(
            Room.school_id == school_id,
            Room.is_active == True,
            Room.is_deleted == False,
        )
        rooms = (await self.session.execute(room_stmt)).scalars().all()

        for rm in rooms:
            if rm.id == conflict.room_id:
                continue
            # Check capacity
            if conflict.section.capacity > rm.capacity:
                continue
            # Check if room is booked at this slot
            booked_stmt = select(ClassTimetableEntry).where(
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.room_id == rm.id,
                ClassTimetableEntry.working_day_id == wd_id,
                ClassTimetableEntry.time_slot_id == ts_id,
                ClassTimetableEntry.is_deleted == False,
            )
            booked = (await self.session.execute(booked_stmt)).scalars().all()
            if not booked:
                suggestions.append(
                    AlternativeSuggestion(
                        room_id=rm.id,
                        room_name=rm.room_name,
                    )
                )

        # 3. Propose Alternative Slots / Days
        # Find slots on working days where section, teacher, and room are all free
        wd_stmt = select(WorkingDay).where(
            WorkingDay.school_id == school_id,
            WorkingDay.is_working == True,
            WorkingDay.is_deleted == False,
        )
        working_days = (await self.session.execute(wd_stmt)).scalars().all()

        ts_stmt = select(TimeSlot).where(
            TimeSlot.school_id == school_id,
            TimeSlot.is_teaching == True,
            TimeSlot.is_break == False,
            TimeSlot.is_deleted == False,
        )
        time_slots = (await self.session.execute(ts_stmt)).scalars().all()

        for wd in working_days:
            for ts in time_slots:
                if ts.working_day_id != wd.id:
                    continue
                if wd.id == wd_id and ts.id == ts_id:
                    continue

                # Check if section has another class scheduled at this slot
                sect_booked = select(ClassTimetableEntry).where(
                    ClassTimetableEntry.school_id == school_id,
                    ClassTimetableEntry.timetable_id == conflict.class_id,  # timetable_id correlates to the class timetable
                    ClassTimetableEntry.working_day_id == wd.id,
                    ClassTimetableEntry.time_slot_id == ts.id,
                    ClassTimetableEntry.is_deleted == False,
                )
                if (await self.session.execute(sect_booked)).scalars().first():
                    continue

                # Check if teacher is busy
                t_booked = select(ClassTimetableEntry).where(
                    ClassTimetableEntry.school_id == school_id,
                    ClassTimetableEntry.teacher_id == conflict.teacher_id,
                    ClassTimetableEntry.working_day_id == wd.id,
                    ClassTimetableEntry.time_slot_id == ts.id,
                    ClassTimetableEntry.is_deleted == False,
                )
                if (await self.session.execute(t_booked)).scalars().first():
                    continue

                # Check if room is busy (if room is assigned)
                if conflict.room_id:
                    rm_booked = select(ClassTimetableEntry).where(
                        ClassTimetableEntry.school_id == school_id,
                        ClassTimetableEntry.room_id == conflict.room_id,
                        ClassTimetableEntry.working_day_id == wd.id,
                        ClassTimetableEntry.time_slot_id == ts.id,
                        ClassTimetableEntry.is_deleted == False,
                    )
                    if (await self.session.execute(rm_booked)).scalars().first():
                        continue

                suggestions.append(
                    AlternativeSuggestion(
                        working_day_id=wd.id,
                        day_name=wd.day_of_week.value,
                        time_slot_id=ts.id,
                        slot_name=ts.name,
                    )
                )

        return suggestions

    async def resolve_automatically(
        self, conflict: ConflictRecord, actor_id: uuid.UUID
    ) -> ConflictResolution:
        """
        Attempts to automatically apply the first valid suggested alternative to resolve the conflict.
        """
        suggestions = await self.suggest_alternatives(conflict)
        if not suggestions:
            raise ResolutionFailedException(
                "Automatic resolution engine failed: no valid alternative suggestion found."
            )

        # Apply the first available suggestion
        s = suggestions[0]
        action_taken = ""

        # Fetch the conflicting ClassTimetableEntry to modify
        entry_stmt = select(ClassTimetableEntry).where(
            ClassTimetableEntry.school_id == conflict.school_id,
            ClassTimetableEntry.working_day_id == conflict.working_day_id,
            ClassTimetableEntry.time_slot_id == conflict.time_slot_id,
            ClassTimetableEntry.teacher_id == conflict.teacher_id,
            ClassTimetableEntry.subject_id == conflict.subject_id,
            ClassTimetableEntry.is_deleted == False,
        )
        entry = (await self.session.execute(entry_stmt)).scalars().first()

        if not entry:
            raise ResolutionFailedException("Conflicting timetable entry not found for re-scheduling.")

        if s.room_id:
            entry.room_id = s.room_id
            action_taken = f"Reassigned room to {s.room_name}."
        elif s.teacher_id:
            entry.teacher_id = s.teacher_id
            action_taken = f"Reassigned teacher to {s.teacher_name}."
        elif s.working_day_id and s.time_slot_id:
            entry.working_day_id = s.working_day_id
            entry.time_slot_id = s.time_slot_id
            action_taken = f"Rescheduled slot to {s.day_name} {s.slot_name}."
        else:
            raise ResolutionFailedException("Invalid suggestion structure proposed.")

        self.session.add(entry)

        # Mark conflict as resolved
        conflict.status = ConflictStatus.RESOLVED
        conflict.resolved_at = datetime.datetime.utcnow()
        conflict.resolved_by = actor_id
        conflict.remarks = "Resolved automatically by conflict resolution engine."
        self.session.add(conflict)

        # Log resolution details
        res = ConflictResolution(
            school_id=conflict.school_id,
            conflict_record_id=conflict.id,
            resolution_strategy="AUTOMATIC",
            action_taken=action_taken,
            resolved_by=actor_id,
            resolved_at=datetime.datetime.utcnow(),
            status="SUCCESS",
        )
        self.session.add(res)
        await self.session.flush()

        return res
