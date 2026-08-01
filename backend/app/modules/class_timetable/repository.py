import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.class_model import SchoolClass
from app.modules.class_timetable.enums import TimetableStatus
from app.modules.class_timetable.models import (
    ClassTimetable,
    ClassTimetableEntry,
    RecurringSchedule,
)
from app.modules.section_management.models import Section
from app.modules.teacher.models import Teacher


class ClassTimetableRepository:
    """
    Repository class executing optimized Async SQLAlchemy queries for timetables,
    timetable entries, and recurring schedules with tenant isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Timetable CRUD ---
    async def get_timetable(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> ClassTimetable | None:
        stmt = (
            select(ClassTimetable)
            .where(
                ClassTimetable.id == id,
                ClassTimetable.school_id == school_id,
                ClassTimetable.is_deleted == False,
            )
            .options(
                joinedload(ClassTimetable.school_class),
                joinedload(ClassTimetable.section),
                joinedload(ClassTimetable.term),
                joinedload(ClassTimetable.academic_year),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_timetable(self, timetable: ClassTimetable) -> ClassTimetable:
        self.session.add(timetable)
        await self.session.flush()
        return timetable

    # --- Timetable Entry CRUD ---
    async def get_timetable_entry(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> ClassTimetableEntry | None:
        stmt = (
            select(ClassTimetableEntry)
            .where(
                ClassTimetableEntry.id == id,
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.is_deleted == False,
            )
            .options(
                joinedload(ClassTimetableEntry.working_day),
                joinedload(ClassTimetableEntry.time_slot),
                joinedload(ClassTimetableEntry.teacher).joinedload(Teacher.employee),
                joinedload(ClassTimetableEntry.subject),
                joinedload(ClassTimetableEntry.room),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_timetable_entry(
        self, entry: ClassTimetableEntry
    ) -> ClassTimetableEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    # --- Recurring Schedule CRUD ---
    async def get_recurring_schedule(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> RecurringSchedule | None:
        stmt = select(RecurringSchedule).where(
            RecurringSchedule.id == id,
            RecurringSchedule.school_id == school_id,
            RecurringSchedule.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_recurring_schedule(
        self, schedule: RecurringSchedule
    ) -> RecurringSchedule:
        self.session.add(schedule)
        await self.session.flush()
        return schedule

    # --- Class, Section, Academic Year, Term Queries ---
    async def get_by_class(
        self, class_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[ClassTimetable]:
        stmt = select(ClassTimetable).where(
            ClassTimetable.class_id == class_id,
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[ClassTimetable]:
        stmt = select(ClassTimetable).where(
            ClassTimetable.section_id == section_id,
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_academic_year(
        self, academic_year_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[ClassTimetable]:
        stmt = select(ClassTimetable).where(
            ClassTimetable.academic_year_id == academic_year_id,
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_weekly_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[ClassTimetableEntry]:
        stmt = (
            select(ClassTimetableEntry)
            .where(
                ClassTimetableEntry.timetable_id == timetable_id,
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.is_deleted == False,
            )
            .options(
                joinedload(ClassTimetableEntry.working_day),
                joinedload(ClassTimetableEntry.time_slot),
                joinedload(ClassTimetableEntry.teacher).joinedload(Teacher.employee),
                joinedload(ClassTimetableEntry.subject),
                joinedload(ClassTimetableEntry.room),
            )
            .order_by(ClassTimetableEntry.period_number.asc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_version_history(
        self,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Sequence[ClassTimetable]:
        stmt = (
            select(ClassTimetable)
            .where(
                ClassTimetable.class_id == class_id,
                ClassTimetable.section_id == section_id,
                ClassTimetable.term_id == term_id,
                ClassTimetable.school_id == school_id,
                ClassTimetable.is_deleted == False,
            )
            .order_by(ClassTimetable.version.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_max_version(
        self,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> int:
        stmt = select(func.max(ClassTimetable.version)).where(
            ClassTimetable.class_id == class_id,
            ClassTimetable.section_id == section_id,
            ClassTimetable.term_id == term_id,
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
        )
        res = (await self.session.execute(stmt)).scalar()
        return res or 0

    async def find_active_published_timetable(
        self,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> ClassTimetable | None:
        stmt = select(ClassTimetable).where(
            ClassTimetable.class_id == class_id,
            ClassTimetable.section_id == section_id,
            ClassTimetable.term_id == term_id,
            ClassTimetable.school_id == school_id,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetable.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- Conflict Verifications ---
    async def check_room_conflict(
        self,
        room_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        school_id: uuid.UUID,
        exclude_entry_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = (
            select(ClassTimetableEntry)
            .join(ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id)
            .where(
                ClassTimetableEntry.room_id == room_id,
                ClassTimetableEntry.working_day_id == working_day_id,
                ClassTimetableEntry.time_slot_id == time_slot_id,
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.is_deleted == False,
                ClassTimetable.status == TimetableStatus.PUBLISHED,
                ClassTimetable.is_deleted == False,
            )
        )
        if exclude_entry_id:
            stmt = stmt.where(ClassTimetableEntry.id != exclude_entry_id)
        res = (await self.session.execute(stmt)).scalars().first()
        return res is not None

    async def check_teacher_conflict(
        self,
        teacher_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        school_id: uuid.UUID,
        exclude_entry_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = (
            select(ClassTimetableEntry)
            .join(ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id)
            .where(
                ClassTimetableEntry.teacher_id == teacher_id,
                ClassTimetableEntry.working_day_id == working_day_id,
                ClassTimetableEntry.time_slot_id == time_slot_id,
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.is_deleted == False,
                ClassTimetable.status == TimetableStatus.PUBLISHED,
                ClassTimetable.is_deleted == False,
            )
        )
        if exclude_entry_id:
            stmt = stmt.where(ClassTimetableEntry.id != exclude_entry_id)
        res = (await self.session.execute(stmt)).scalars().first()
        return res is not None

    # --- List & Search Filters ---
    async def list_timetables(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        status: TimetableStatus | None = None,
        is_active: bool | None = None,
        sort_by: str = "created_at",
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ClassTimetable]:
        stmt = select(ClassTimetable).where(
            ClassTimetable.school_id == school_id,
            ClassTimetable.is_deleted == False,
        )

        # Filters
        if academic_year_id is not None:
            stmt = stmt.where(ClassTimetable.academic_year_id == academic_year_id)
        if term_id is not None:
            stmt = stmt.where(ClassTimetable.term_id == term_id)
        if class_id is not None:
            stmt = stmt.where(ClassTimetable.class_id == class_id)
        if section_id is not None:
            stmt = stmt.where(ClassTimetable.section_id == section_id)
        if status is not None:
            stmt = stmt.where(ClassTimetable.status == status)
        if is_active is not None:
            stmt = stmt.where(ClassTimetable.is_active == is_active)

        # Sorting
        if sort_by == "class":
            stmt = stmt.join(
                SchoolClass, ClassTimetable.class_id == SchoolClass.id
            ).order_by(SchoolClass.name.asc())
        elif sort_by == "section":
            stmt = stmt.join(Section, ClassTimetable.section_id == Section.id).order_by(
                Section.name.asc()
            )
        else:
            stmt = stmt.order_by(ClassTimetable.created_at.desc())

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()
