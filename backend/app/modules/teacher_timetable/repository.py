import uuid
from collections.abc import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.class_timetable.enums import TimetableStatus
from app.modules.class_timetable.models import ClassTimetable, ClassTimetableEntry
from app.modules.employee.models import Employee
from app.modules.teacher.models import Teacher
from app.modules.teacher_timetable.enums import TeacherTimetableStatus
from app.modules.teacher_timetable.models import (
    TeacherAvailability,
    TeacherTimetable,
    TeacherTimetableEntry,
)


class TeacherTimetableRepository:
    """
    Repository class executing optimized Async SQLAlchemy queries for teacher timetables,
    timetable entries, and availability blocks with tenant isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Timetable CRUD ---
    async def get_timetable(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherTimetable | None:
        stmt = (
            select(TeacherTimetable)
            .where(
                TeacherTimetable.id == id,
                TeacherTimetable.school_id == school_id,
                TeacherTimetable.is_deleted == False,
            )
            .options(
                joinedload(TeacherTimetable.teacher).joinedload(Teacher.employee),
                joinedload(TeacherTimetable.academic_year),
                joinedload(TeacherTimetable.term),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_timetable(self, timetable: TeacherTimetable) -> TeacherTimetable:
        self.session.add(timetable)
        await self.session.flush()
        return timetable

    # --- Timetable Entry CRUD ---
    async def get_timetable_entry(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherTimetableEntry | None:
        stmt = (
            select(TeacherTimetableEntry)
            .where(
                TeacherTimetableEntry.id == id,
                TeacherTimetableEntry.school_id == school_id,
                TeacherTimetableEntry.is_deleted == False,
            )
            .options(
                joinedload(TeacherTimetableEntry.working_day),
                joinedload(TeacherTimetableEntry.time_slot),
                joinedload(TeacherTimetableEntry.school_class),
                joinedload(TeacherTimetableEntry.section),
                joinedload(TeacherTimetableEntry.subject),
                joinedload(TeacherTimetableEntry.room),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_timetable_entry(
        self, entry: TeacherTimetableEntry
    ) -> TeacherTimetableEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    # --- Availability CRUD ---
    async def get_availability(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherAvailability | None:
        stmt = select(TeacherAvailability).where(
            TeacherAvailability.id == id,
            TeacherAvailability.school_id == school_id,
            TeacherAvailability.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_availability(
        self, availability: TeacherAvailability
    ) -> TeacherAvailability:
        self.session.add(availability)
        await self.session.flush()
        return availability

    async def lookup_availability(
        self,
        teacher_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> TeacherAvailability | None:
        stmt = select(TeacherAvailability).where(
            TeacherAvailability.teacher_id == teacher_id,
            TeacherAvailability.working_day_id == working_day_id,
            TeacherAvailability.time_slot_id == time_slot_id,
            TeacherAvailability.school_id == school_id,
            TeacherAvailability.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- Specific queries & filters ---
    async def get_by_teacher(
        self, teacher_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[TeacherTimetable]:
        stmt = select(TeacherTimetable).where(
            TeacherTimetable.teacher_id == teacher_id,
            TeacherTimetable.school_id == school_id,
            TeacherTimetable.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_weekly_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[TeacherTimetableEntry]:
        stmt = (
            select(TeacherTimetableEntry)
            .where(
                TeacherTimetableEntry.teacher_timetable_id == timetable_id,
                TeacherTimetableEntry.school_id == school_id,
                TeacherTimetableEntry.is_deleted == False,
            )
            .options(
                joinedload(TeacherTimetableEntry.working_day),
                joinedload(TeacherTimetableEntry.time_slot),
                joinedload(TeacherTimetableEntry.school_class),
                joinedload(TeacherTimetableEntry.section),
                joinedload(TeacherTimetableEntry.subject),
                joinedload(TeacherTimetableEntry.room),
            )
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_availabilities_by_teacher(
        self, teacher_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[TeacherAvailability]:
        stmt = (
            select(TeacherAvailability)
            .where(
                TeacherAvailability.teacher_id == teacher_id,
                TeacherAvailability.school_id == school_id,
                TeacherAvailability.is_deleted == False,
            )
            .options(
                joinedload(TeacherAvailability.working_day),
                joinedload(TeacherAvailability.time_slot),
            )
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_version_history(
        self,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Sequence[TeacherTimetable]:
        stmt = (
            select(TeacherTimetable)
            .where(
                TeacherTimetable.teacher_id == teacher_id,
                TeacherTimetable.academic_year_id == academic_year_id,
                TeacherTimetable.term_id == term_id,
                TeacherTimetable.school_id == school_id,
                TeacherTimetable.is_deleted == False,
            )
            .order_by(TeacherTimetable.version.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_max_version(
        self,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> int:
        stmt = select(func.max(TeacherTimetable.version)).where(
            TeacherTimetable.teacher_id == teacher_id,
            TeacherTimetable.academic_year_id == academic_year_id,
            TeacherTimetable.term_id == term_id,
            TeacherTimetable.school_id == school_id,
            TeacherTimetable.is_deleted == False,
        )
        res = (await self.session.execute(stmt)).scalar()
        return res or 0

    async def find_active_published_timetable(
        self,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> TeacherTimetable | None:
        stmt = select(TeacherTimetable).where(
            TeacherTimetable.teacher_id == teacher_id,
            TeacherTimetable.academic_year_id == academic_year_id,
            TeacherTimetable.term_id == term_id,
            TeacherTimetable.school_id == school_id,
            TeacherTimetable.status == TeacherTimetableStatus.PUBLISHED,
            TeacherTimetable.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_published_class_entries_for_teacher(
        self,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Sequence[ClassTimetableEntry]:
        stmt = (
            select(ClassTimetableEntry)
            .join(ClassTimetable, ClassTimetableEntry.timetable_id == ClassTimetable.id)
            .where(
                ClassTimetableEntry.teacher_id == teacher_id,
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.is_deleted == False,
                ClassTimetable.academic_year_id == academic_year_id,
                ClassTimetable.term_id == term_id,
                ClassTimetable.status == TimetableStatus.PUBLISHED,
                ClassTimetable.is_deleted == False,
            )
            .options(joinedload(ClassTimetableEntry.timetable))
        )
        return (await self.session.execute(stmt)).scalars().all()

    # --- Filtering and list retrieval ---
    async def list_timetables(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        working_day_id: uuid.UUID | None = None,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        status: TeacherTimetableStatus | None = None,
        sort_by: str = "created_at",
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[TeacherTimetable]:
        stmt = select(TeacherTimetable).where(
            TeacherTimetable.school_id == school_id,
            TeacherTimetable.is_deleted == False,
        )

        # Basic filters
        if teacher_id is not None:
            stmt = stmt.where(TeacherTimetable.teacher_id == teacher_id)
        if academic_year_id is not None:
            stmt = stmt.where(TeacherTimetable.academic_year_id == academic_year_id)
        if term_id is not None:
            stmt = stmt.where(TeacherTimetable.term_id == term_id)
        if status is not None:
            stmt = stmt.where(TeacherTimetable.status == status)

        joined_teacher = False

        # Department filter
        if department_id is not None:
            stmt = stmt.join(Teacher, TeacherTimetable.teacher_id == Teacher.id).join(
                Employee, Teacher.employee_id == Employee.id
            ).where(Employee.department_id == department_id)
            joined_teacher = True

        # Subject or Working Day filters
        if subject_id is not None or working_day_id is not None:
            stmt = stmt.join(
                TeacherTimetableEntry,
                and_(
                    TeacherTimetableEntry.teacher_timetable_id == TeacherTimetable.id,
                    TeacherTimetableEntry.is_deleted == False
                )
            )
            if subject_id is not None:
                stmt = stmt.where(TeacherTimetableEntry.subject_id == subject_id)
            if working_day_id is not None:
                stmt = stmt.where(TeacherTimetableEntry.working_day_id == working_day_id)

        # Sorting
        if sort_by == "teacher_name":
            # Joins Teacher -> Employee to sort by name
            if not joined_teacher:
                stmt = stmt.join(Teacher, TeacherTimetable.teacher_id == Teacher.id).join(
                    Employee, Teacher.employee_id == Employee.id
                )
            stmt = stmt.order_by(Employee.first_name.asc(), Employee.last_name.asc())
        else:
            stmt = stmt.order_by(TeacherTimetable.created_at.desc())

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()
