import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.class_timetable.models import ClassTimetable, ClassTimetableEntry
from app.modules.section_management.models import Section
from app.modules.teacher_subject_allocation.models import (
    TeacherWorkload,
)
from app.modules.teacher_timetable.models import TeacherAvailability
from app.modules.timetable_conflict.enums import ConflictSeverity, ConflictType

logger = logging.getLogger(__name__)


class TimetableConflictEngine:
    """
    Validation engine evaluating timetable layouts to catch overlap double-bookings,
    workload exhaustion, room capacity deficits, and calendar exceptions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def detect_conflicts(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        section_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """
        Scans class schedules to identify all rule violations.
        Returns a list of conflict dictionary objects.
        """
        conflicts: list[dict[str, Any]] = []

        # 1. Load active class timetable entries
        tt_stmt = select(ClassTimetable).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.academic_year_id == academic_year_id,
            ClassTimetable.term_id == term_id,
            ClassTimetable.is_deleted == False,
        )
        if section_id:
            tt_stmt = tt_stmt.where(ClassTimetable.section_id == section_id)
        timetables = (await self.session.execute(tt_stmt)).scalars().all()
        timetable_ids = [tt.id for tt in timetables]

        if not timetable_ids:
            return conflicts

        entry_stmt = (
            select(ClassTimetableEntry)
            .options(
                joinedload(ClassTimetableEntry.timetable),
                joinedload(ClassTimetableEntry.teacher),
                joinedload(ClassTimetableEntry.subject),
                joinedload(ClassTimetableEntry.room),
                joinedload(ClassTimetableEntry.working_day),
                joinedload(ClassTimetableEntry.time_slot),
            )
            .where(
                ClassTimetableEntry.timetable_id.in_(timetable_ids),
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.is_deleted == False,
            )
        )
        entries = (await self.session.execute(entry_stmt)).scalars().all()

        # Load teacher availabilities
        ta_stmt = select(TeacherAvailability).where(
            TeacherAvailability.school_id == school_id,
            TeacherAvailability.is_deleted == False,
        )
        availabilities = (await self.session.execute(ta_stmt)).scalars().all()
        avail_map = {
            (a.teacher_id, a.working_day_id, a.time_slot_id): a.availability_status.value
            for a in availabilities
        }

        # Load workloads
        wl_stmt = select(TeacherWorkload).where(
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        workloads = (await self.session.execute(wl_stmt)).scalars().all()
        wl_map = {w.teacher_id: w.maximum_weekly_periods for w in workloads}

        # Load section capacities
        sect_stmt = select(Section).where(
            Section.school_id == school_id,
            Section.is_deleted == False,
        )
        sections = (await self.session.execute(sect_stmt)).scalars().all()
        sect_caps = {s.id: s.capacity for s in sections}

        # Tracks allocations for double-booking checks
        teacher_slots: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], list[ClassTimetableEntry]] = {}
        room_slots: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], list[ClassTimetableEntry]] = {}
        class_slots: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], list[ClassTimetableEntry]] = {}
        teacher_weekly_allocations: dict[uuid.UUID, int] = {}

        for entry in entries:
            t_id = entry.teacher_id
            r_id = entry.room_id
            wd_id = entry.working_day_id
            ts_id = entry.time_slot_id
            sect_id = entry.timetable.section_id

            # Weekly workload count
            teacher_weekly_allocations[t_id] = teacher_weekly_allocations.get(t_id, 0) + 1

            # Grouping for double booking checks
            teacher_slots.setdefault((t_id, wd_id, ts_id), []).append(entry)
            if r_id:
                room_slots.setdefault((r_id, wd_id, ts_id), []).append(entry)
            class_slots.setdefault((sect_id, wd_id, ts_id), []).append(entry)

            # 1. Teacher Availability Conflict
            avail = avail_map.get((t_id, wd_id, ts_id))
            if avail == "UNAVAILABLE":
                conflicts.append({
                    "conflict_type": ConflictType.TEACHER_AVAILABILITY,
                    "severity": ConflictSeverity.CRITICAL,
                    "class_id": entry.timetable.class_id,
                    "section_id": sect_id,
                    "teacher_id": t_id,
                    "room_id": r_id,
                    "subject_id": entry.subject_id,
                    "working_day_id": wd_id,
                    "time_slot_id": ts_id,
                    "description": f"Teacher {entry.teacher.teacher_code} scheduled during marked unavailable slot.",
                })

            # 2. Room Capacity Conflict
            if r_id and entry.room:
                sect_cap = sect_caps.get(sect_id, 0)
                room_cap = entry.room.capacity
                if sect_cap > room_cap:
                    conflicts.append({
                        "conflict_type": ConflictType.ROOM_CAPACITY,
                        "severity": ConflictSeverity.WARNING,
                        "class_id": entry.timetable.class_id,
                        "section_id": sect_id,
                        "teacher_id": t_id,
                        "room_id": r_id,
                        "subject_id": entry.subject_id,
                        "working_day_id": wd_id,
                        "time_slot_id": ts_id,
                        "description": f"Section capacity ({sect_cap}) exceeds Room capacity ({room_cap}) for {entry.room.room_name}.",
                    })

            # 3. Holiday Conflict (Optional extension)
            # 4. Teacher Leave Conflict (Optional extension)
            pass

        # 5. Teacher Double Bookings
        for (t_id, wd_id, ts_id), slot_entries in teacher_slots.items():
            if len(slot_entries) > 1:
                first = slot_entries[0]
                conflicts.append({
                    "conflict_type": ConflictType.TEACHER_DOUBLE_BOOKING,
                    "severity": ConflictSeverity.CRITICAL,
                    "class_id": first.timetable.class_id,
                    "section_id": first.timetable.section_id,
                    "teacher_id": t_id,
                    "room_id": first.room_id,
                    "subject_id": first.subject_id,
                    "working_day_id": wd_id,
                    "time_slot_id": ts_id,
                    "description": f"Teacher double booked across {len(slot_entries)} sections at slot.",
                })

        # 6. Room Double Bookings
        for (r_id, wd_id, ts_id), slot_entries in room_slots.items():
            if len(slot_entries) > 1:
                first = slot_entries[0]
                conflicts.append({
                    "conflict_type": ConflictType.ROOM_DOUBLE_BOOKING,
                    "severity": ConflictSeverity.CRITICAL,
                    "class_id": first.timetable.class_id,
                    "section_id": first.timetable.section_id,
                    "teacher_id": first.teacher_id,
                    "room_id": r_id,
                    "subject_id": first.subject_id,
                    "working_day_id": wd_id,
                    "time_slot_id": ts_id,
                    "description": f"Room double booked across {len(slot_entries)} classes at slot.",
                })

        # 7. Class/Section Double Bookings
        for (sect_id, wd_id, ts_id), slot_entries in class_slots.items():
            if len(slot_entries) > 1:
                first = slot_entries[0]
                conflicts.append({
                    "conflict_type": ConflictType.CLASS_DOUBLE_BOOKING,
                    "severity": ConflictSeverity.CRITICAL,
                    "class_id": first.timetable.class_id,
                    "section_id": sect_id,
                    "teacher_id": first.teacher_id,
                    "room_id": first.room_id,
                    "subject_id": first.subject_id,
                    "working_day_id": wd_id,
                    "time_slot_id": ts_id,
                    "description": "Class section double booked with multiple subjects at slot.",
                })

        # 8. Workload Conflicts
        for t_id, alloc_count in teacher_weekly_allocations.items():
            max_wl = wl_map.get(t_id, 24)
            if alloc_count > max_wl:
                # Find one matching entry to link metadata
                first_entry = next(e for e in entries if e.teacher_id == t_id)
                conflicts.append({
                    "conflict_type": ConflictType.MAX_WORKLOAD,
                    "severity": ConflictSeverity.WARNING,
                    "class_id": first_entry.timetable.class_id,
                    "section_id": first_entry.timetable.section_id,
                    "teacher_id": t_id,
                    "room_id": first_entry.room_id,
                    "subject_id": first_entry.subject_id,
                    "working_day_id": first_entry.working_day_id,
                    "time_slot_id": first_entry.time_slot_id,
                    "description": f"Teacher workload ({alloc_count}) exceeds weekly maximum allowed ({max_wl}).",
                })

        return conflicts
