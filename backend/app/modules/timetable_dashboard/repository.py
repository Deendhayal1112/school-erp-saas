"""
Repository executing optimized Async SQLAlchemy aggregated queries
for Timetable Dashboard, Analytics & Reports.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.class_model import SchoolClass
from app.modules.academic_calendar.models import WorkingDay
from app.modules.class_timetable.enums import TimetableStatus
from app.modules.class_timetable.models import ClassTimetable, ClassTimetableEntry
from app.modules.employee.models import Employee
from app.modules.room.models import Room
from app.modules.section_management.models import Section
from app.modules.subject_management.models import Subject
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import TeacherWorkload
from app.modules.term.models import Term
from app.modules.time_slot.models import TimeSlot
from app.modules.timetable_adjustment.enums import SubstitutionStatus
from app.modules.timetable_adjustment.models import TeacherSubstitution
from app.modules.timetable_conflict.enums import ConflictStatus
from app.modules.timetable_conflict.models import ConflictRecord


class TimetableDashboardRepository:
    """
    Repository layer executing tenant-isolated, optimized queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -----------------------------------------------------------------------
    # KPI Queries
    # -----------------------------------------------------------------------
    async def get_total_timetables(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(ClassTimetable.id)).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_published_timetables_count(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(ClassTimetable.id)).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetable.is_deleted == False,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_draft_timetables_count(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(ClassTimetable.id)).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.status == TimetableStatus.DRAFT,
            ClassTimetable.is_deleted == False,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_total_classes_scheduled(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(func.distinct(ClassTimetable.class_id))).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetable.is_deleted == False,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_total_teachers_scheduled(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(func.distinct(ClassTimetableEntry.teacher_id))).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_total_rooms_utilized(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(func.distinct(ClassTimetableEntry.room_id))).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.room_id.isnot(None),
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_avg_teacher_workload(self, school_id: uuid.UUID) -> float:
        stmt = select(
            func.avg(
                cast(TeacherWorkload.allocated_periods, Float) /
                func.nullif(cast(TeacherWorkload.maximum_weekly_periods, Float), 0)
            )
        ).where(
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        val = (await self.session.execute(stmt)).scalar()
        return round((val or 0.0) * 100.0, 2)

    async def get_avg_room_utilization(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> float:
        rooms_count = (await self.session.execute(
            select(func.count(Room.id)).where(
                Room.school_id == school_id,
                Room.is_deleted == False,
                Room.is_bookable == True,
            )
        )).scalar() or 0

        working_days_count = (await self.session.execute(
            select(func.count(WorkingDay.id)).where(
                WorkingDay.school_id == school_id,
                WorkingDay.is_deleted == False,
                WorkingDay.is_working == True,
            )
        )).scalar() or 0

        time_slots_count = (await self.session.execute(
            select(func.count(TimeSlot.id)).where(
                TimeSlot.school_id == school_id,
                TimeSlot.is_deleted == False,
                TimeSlot.is_teaching == True,
            )
        )).scalar() or 0

        total_room_slots = rooms_count * working_days_count * time_slots_count

        stmt = select(func.count(ClassTimetableEntry.id)).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.room_id.isnot(None),
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        occupied_slots = (await self.session.execute(stmt)).scalar() or 0

        if total_room_slots > 0:
            return round((occupied_slots / total_room_slots) * 100.0, 2)
        return 0.0

    async def get_total_weekly_periods(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> int:
        stmt = select(func.count(ClassTimetableEntry.id)).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_substitutions_today(self, school_id: uuid.UUID) -> int:
        today = date.today()
        stmt = select(func.count(TeacherSubstitution.id)).where(
            TeacherSubstitution.school_id == school_id,
            TeacherSubstitution.is_deleted == False,
            TeacherSubstitution.effective_date == today,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_conflicts_resolved_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(ConflictRecord.id)).where(
            ConflictRecord.school_id == school_id,
            ConflictRecord.is_deleted == False,
            ConflictRecord.status == ConflictStatus.RESOLVED,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    async def get_conflicts_pending_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(ConflictRecord.id)).where(
            ConflictRecord.school_id == school_id,
            ConflictRecord.is_deleted == False,
            ConflictRecord.status == ConflictStatus.PENDING,
        )
        return (await self.session.execute(stmt)).scalar() or 0

    # -----------------------------------------------------------------------
    # Analytics Queries
    # -----------------------------------------------------------------------
    async def get_teacher_workload_distribution(self, school_id: uuid.UUID) -> dict[str, int]:
        stmt = select(TeacherWorkload.allocated_periods).where(
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        workloads = (await self.session.execute(stmt)).scalars().all()
        buckets = {"<10": 0, "10-15": 0, "15-20": 0, "20+": 0}
        for w in workloads:
            if w < 10:
                buckets["<10"] += 1
            elif w <= 15:
                buckets["10-15"] += 1
            elif w <= 20:
                buckets["15-20"] += 1
            else:
                buckets["20+"] += 1
        return buckets

    async def get_room_utilization_per_room(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[tuple[str, float]]:
        working_days_count = (await self.session.execute(
            select(func.count(WorkingDay.id)).where(
                WorkingDay.school_id == school_id,
                WorkingDay.is_deleted == False,
                WorkingDay.is_working == True,
            )
        )).scalar() or 0

        time_slots_count = (await self.session.execute(
            select(func.count(TimeSlot.id)).where(
                TimeSlot.school_id == school_id,
                TimeSlot.is_deleted == False,
                TimeSlot.is_teaching == True,
            )
        )).scalar() or 0

        room_capacity = working_days_count * time_slots_count

        rooms_stmt = select(Room.id, Room.room_name).where(
            Room.school_id == school_id,
            Room.is_deleted == False,
            Room.is_bookable == True,
        )
        rooms = (await self.session.execute(rooms_stmt)).all()
        room_names = {r.id: r.room_name for r in rooms}

        entries_stmt = select(
            ClassTimetableEntry.room_id,
            func.count(ClassTimetableEntry.id)
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetableEntry.room_id.isnot(None),
        )
        if academic_year_id:
            entries_stmt = entries_stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            entries_stmt = entries_stmt.where(ClassTimetable.term_id == term_id)
        entries_stmt = entries_stmt.group_by(ClassTimetableEntry.room_id)

        counts: dict[uuid.UUID | None, int] = {row[0]: row[1] for row in (await self.session.execute(entries_stmt)).all()}

        data = []
        for rid, name in room_names.items():
            cnt = counts.get(rid, 0)
            util = round((cnt / room_capacity) * 100.0, 2) if room_capacity > 0 else 0.0
            data.append((name, util))
        return data

    async def get_subject_distribution(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[tuple[str, int]]:
        stmt = select(
            Subject.subject_name,
            func.count(ClassTimetableEntry.id)
        ).join(
            ClassTimetableEntry, ClassTimetableEntry.subject_id == Subject.id
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            Subject.school_id == school_id,
            Subject.is_deleted == False,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        stmt = stmt.group_by(Subject.id, Subject.subject_name)
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

    async def get_class_wise_period_count(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[tuple[str, str, int]]:
        stmt = select(
            SchoolClass.name.label("class_name"),
            Section.name.label("section_name"),
            func.count(ClassTimetableEntry.id)
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).join(
            SchoolClass, ClassTimetable.class_id == SchoolClass.id
        ).join(
            Section, ClassTimetable.section_id == Section.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        stmt = stmt.group_by(SchoolClass.id, SchoolClass.name, Section.id, Section.name)
        return [(row[0], row[1], row[2]) for row in (await self.session.execute(stmt)).all()]

    async def get_teacher_wise_period_count(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[tuple[str, str, int]]:
        stmt = select(
            Employee.first_name,
            Employee.last_name,
            func.count(ClassTimetableEntry.id)
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).join(
            Teacher, ClassTimetableEntry.teacher_id == Teacher.id
        ).join(
            Employee, Teacher.employee_id == Employee.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        stmt = stmt.group_by(Employee.id, Employee.first_name, Employee.last_name)
        return [(row[0], row[1], row[2]) for row in (await self.session.execute(stmt)).all()]

    async def get_daily_teaching_hours(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[tuple[Any, float]]:
        stmt = select(
            WorkingDay.day_of_week,
            func.sum(TimeSlot.duration_minutes) / 60.0
        ).join(
            ClassTimetableEntry, ClassTimetableEntry.working_day_id == WorkingDay.id
        ).join(
            TimeSlot, ClassTimetableEntry.time_slot_id == TimeSlot.id
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            WorkingDay.school_id == school_id,
            WorkingDay.is_deleted == False,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        stmt = stmt.group_by(WorkingDay.id, WorkingDay.day_of_week)
        return [(row[0], float(row[1] or 0)) for row in (await self.session.execute(stmt)).all()]

    async def get_weekly_teaching_hours(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[tuple[date, float]]:
        stmt = select(
            ClassTimetable.effective_from,
            func.sum(TimeSlot.duration_minutes) / 60.0
        ).join(
            ClassTimetableEntry, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).join(
            TimeSlot, ClassTimetableEntry.time_slot_id == TimeSlot.id
        ).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetableEntry.is_deleted == False,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        stmt = stmt.group_by(ClassTimetable.effective_from)
        results = (await self.session.execute(stmt)).all()

        weekly_data: dict[date, float] = {}
        for eff_date, hours in results:
            if not eff_date:
                continue
            start_of_week = eff_date - timedelta(days=eff_date.weekday())
            weekly_data[start_of_week] = weekly_data.get(start_of_week, 0.0) + float(hours)
        return sorted(weekly_data.items())

    async def get_timetable_utilization(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None
    ) -> list[tuple[str, int, int]]:
        stmt = select(
            Term.name,
            func.sum(case((ClassTimetable.status == TimetableStatus.PUBLISHED, 1), else_=0)),
            func.count(ClassTimetable.id)
        ).join(
            ClassTimetable, ClassTimetable.term_id == Term.id
        ).where(
            Term.school_id == school_id,
            Term.is_deleted == False,
            ClassTimetable.is_deleted == False,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        stmt = stmt.group_by(Term.id, Term.name)
        results = (await self.session.execute(stmt)).all()
        return [(r[0], r[1] or 0, r[2] or 0) for r in results]

    async def get_substitution_trends(self, school_id: uuid.UUID) -> list[tuple[str, int]]:
        stmt = select(
            TeacherSubstitution.effective_date,
            func.count(TeacherSubstitution.id)
        ).where(
            TeacherSubstitution.school_id == school_id,
            TeacherSubstitution.is_deleted == False,
        ).group_by(TeacherSubstitution.effective_date)
        results = (await self.session.execute(stmt)).all()

        trends: dict[str, int] = {}
        for dt, count in results:
            if not dt:
                continue
            month_str = dt.strftime("%Y-%m")
            trends[month_str] = trends.get(month_str, 0) + count
        return sorted(trends.items())

    async def get_conflict_trends(self, school_id: uuid.UUID) -> list[tuple[str, int]]:
        stmt = select(
            ConflictRecord.detected_at,
            func.count(ConflictRecord.id)
        ).where(
            ConflictRecord.school_id == school_id,
            ConflictRecord.is_deleted == False,
        ).group_by(ConflictRecord.detected_at)
        results = (await self.session.execute(stmt)).all()

        trends: dict[str, int] = {}
        for dt, count in results:
            if not dt:
                continue
            month_str = dt.strftime("%Y-%m")
            trends[month_str] = trends.get(month_str, 0) + count
        return sorted(trends.items())

    # -----------------------------------------------------------------------
    # Weekly Timetable Heatmap (Helper for Charts)
    # -----------------------------------------------------------------------
    async def get_weekly_timetable_heatmap(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            WorkingDay.day_of_week,
            TimeSlot.name.label("time_slot_name"),
            func.count(ClassTimetableEntry.id)
        ).join(
            ClassTimetableEntry, ClassTimetableEntry.working_day_id == WorkingDay.id
        ).join(
            TimeSlot, ClassTimetableEntry.time_slot_id == TimeSlot.id
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            WorkingDay.school_id == school_id,
            WorkingDay.is_deleted == False,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
        )
        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        stmt = stmt.group_by(WorkingDay.day_of_week, TimeSlot.id, TimeSlot.name)
        results = (await self.session.execute(stmt)).all()
        return [
            {
                "day_name": r[0].value if hasattr(r[0], "value") else str(r[0]),
                "time_slot": r[1],
                "count": r[2] or 0,
            }
            for r in results
        ]

    # -----------------------------------------------------------------------
    # Detailed Reports & Filtering Queries
    # -----------------------------------------------------------------------
    async def query_master_timetable(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        working_day_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ClassTimetableEntry]:
        stmt = select(ClassTimetableEntry).options(
            joinedload(ClassTimetableEntry.timetable).joinedload(ClassTimetable.school_class),
            joinedload(ClassTimetableEntry.timetable).joinedload(ClassTimetable.section),
            joinedload(ClassTimetableEntry.teacher).joinedload(Teacher.employee),
            joinedload(ClassTimetableEntry.subject),
            joinedload(ClassTimetableEntry.room),
            joinedload(ClassTimetableEntry.working_day),
            joinedload(ClassTimetableEntry.time_slot),
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
        )

        if academic_year_id:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        if teacher_id:
            stmt = stmt.where(ClassTimetableEntry.teacher_id == teacher_id)
        if class_id:
            stmt = stmt.where(ClassTimetable.class_id == class_id)
        if section_id:
            stmt = stmt.where(ClassTimetable.section_id == section_id)
        if room_id:
            stmt = stmt.where(ClassTimetableEntry.room_id == room_id)
        if subject_id:
            stmt = stmt.where(ClassTimetableEntry.subject_id == subject_id)
        if working_day_id:
            stmt = stmt.where(ClassTimetableEntry.working_day_id == working_day_id)

        stmt = stmt.order_by(
            ClassTimetableEntry.period_number.asc()
        ).offset(skip).limit(limit)

        return list((await self.session.execute(stmt)).scalars().all())

    async def query_room_utilization_report(
        self,
        school_id: uuid.UUID,
        room_id: uuid.UUID | None = None,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        working_days_count = (await self.session.execute(
            select(func.count(WorkingDay.id)).where(
                WorkingDay.school_id == school_id,
                WorkingDay.is_deleted == False,
                WorkingDay.is_working == True,
            )
        )).scalar() or 0

        time_slots_count = (await self.session.execute(
            select(func.count(TimeSlot.id)).where(
                TimeSlot.school_id == school_id,
                TimeSlot.is_deleted == False,
                TimeSlot.is_teaching == True,
            )
        )).scalar() or 0

        total_slots = working_days_count * time_slots_count

        rooms_stmt = select(Room).where(
            Room.school_id == school_id,
            Room.is_deleted == False,
        )
        if room_id:
            rooms_stmt = rooms_stmt.where(Room.id == room_id)
        rooms_stmt = rooms_stmt.offset(skip).limit(limit)
        rooms = list((await self.session.execute(rooms_stmt)).scalars().all())

        entries_stmt = select(
            ClassTimetableEntry.room_id,
            func.count(ClassTimetableEntry.id)
        ).join(
            ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id
        ).where(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
            ClassTimetable.is_deleted == False,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetableEntry.room_id.isnot(None),
        )
        if academic_year_id:
            entries_stmt = entries_stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id:
            entries_stmt = entries_stmt.where(ClassTimetable.term_id == term_id)
        entries_stmt = entries_stmt.group_by(ClassTimetableEntry.room_id)

        counts: dict[uuid.UUID | None, int] = {row[0]: row[1] for row in (await self.session.execute(entries_stmt)).all()}

        report_data = []
        for r in rooms:
            cnt = counts.get(r.id, 0)
            util = round((cnt / total_slots) * 100.0, 2) if total_slots > 0 else 0.0
            report_data.append({
                "room_name": r.room_name,
                "room_type": r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
                "capacity": r.capacity,
                "scheduled_periods": cnt,
                "total_slots": total_slots,
                "utilization_percentage": util,
            })
        return report_data

    async def query_teacher_workload_report(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = select(TeacherWorkload).options(
            joinedload(TeacherWorkload.teacher).joinedload(Teacher.employee)
        ).where(
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        if teacher_id:
            stmt = stmt.where(TeacherWorkload.teacher_id == teacher_id)
        stmt = stmt.offset(skip).limit(limit)
        workloads = list((await self.session.execute(stmt)).scalars().all())

        report_data = []
        for w in workloads:
            emp = w.teacher.employee if w.teacher else None
            t_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown Teacher"
            max_p = w.maximum_weekly_periods
            alloc_p = w.allocated_periods
            util = round((alloc_p / max_p) * 100.0, 2) if max_p > 0 else 0.0
            report_data.append({
                "teacher_name": t_name,
                "maximum_weekly_periods": max_p,
                "allocated_periods": alloc_p,
                "remaining_periods": w.remaining_periods,
                "daily_limit": w.daily_limit,
                "consecutive_period_limit": w.consecutive_period_limit,
                "utilization_percentage": util,
            })
        return report_data

    async def query_conflict_report(
        self,
        school_id: uuid.UUID,
        status: ConflictStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ConflictRecord]:
        stmt = select(ConflictRecord).options(
            joinedload(ConflictRecord.school_class),
            joinedload(ConflictRecord.section),
            joinedload(ConflictRecord.teacher).joinedload(Teacher.employee),
            joinedload(ConflictRecord.subject),
            joinedload(ConflictRecord.working_day),
            joinedload(ConflictRecord.time_slot),
            joinedload(ConflictRecord.resolver),
        ).where(
            ConflictRecord.school_id == school_id,
            ConflictRecord.is_deleted == False,
        )

        if status:
            stmt = stmt.where(ConflictRecord.status == status)
        if date_from:
            stmt = stmt.where(func.date(ConflictRecord.detected_at) >= date_from)
        if date_to:
            stmt = stmt.where(func.date(ConflictRecord.detected_at) <= date_to)

        stmt = stmt.order_by(ConflictRecord.detected_at.desc()).offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def query_substitution_report(
        self,
        school_id: uuid.UUID,
        status: SubstitutionStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[TeacherSubstitution]:
        stmt = select(TeacherSubstitution).options(
            joinedload(TeacherSubstitution.original_teacher).joinedload(Teacher.employee),
            joinedload(TeacherSubstitution.substitute_teacher).joinedload(Teacher.employee),
            joinedload(TeacherSubstitution.school_class),
            joinedload(TeacherSubstitution.section),
            joinedload(TeacherSubstitution.subject),
            joinedload(TeacherSubstitution.working_day),
            joinedload(TeacherSubstitution.time_slot),
            joinedload(TeacherSubstitution.approver),
        ).where(
            TeacherSubstitution.school_id == school_id,
            TeacherSubstitution.is_deleted == False,
        )

        if status:
            stmt = stmt.where(TeacherSubstitution.status == status)
        if date_from:
            stmt = stmt.where(TeacherSubstitution.effective_date >= date_from)
        if date_to:
            stmt = stmt.where(TeacherSubstitution.effective_date <= date_to)

        stmt = stmt.order_by(TeacherSubstitution.effective_date.desc()).offset(skip).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())
