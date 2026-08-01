import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.exceptions.exceptions import NotFoundException
from app.models.class_model import SchoolClass
from app.models.user import User
from app.modules.academic_calendar.enums import DayOfWeek
from app.modules.academic_calendar.models import WorkingDay
from app.modules.academic_year.exceptions import AcademicYearNotFoundException
from app.modules.academic_year.models import AcademicYear
from app.modules.class_timetable.enums import TimetableStatus
from app.modules.class_timetable.exceptions import (
    ClassTimetableEntryNotFoundException,
    ClassTimetableNotFoundException,
    DuplicateTimetableEntryException,
    RoomNotAvailableException,
    TeacherNotAvailableException,
    TimetableLockedException,
)
from app.modules.class_timetable.models import (
    ClassTimetable,
    ClassTimetableEntry,
    RecurringSchedule,
)
from app.modules.class_timetable.repository import ClassTimetableRepository
from app.modules.class_timetable.schemas import (
    ClassTimetableCreate,
    ClassTimetableEntryCreate,
    ClassTimetableEntryUpdate,
    ClassTimetableUpdate,
    DayScheduleSummary,
    TimetableCloneRequest,
    TimetableEntrySummary,
    WeeklyScheduleResponse,
)
from app.modules.class_timetable.validators import (
    validate_time_slot_is_teaching,
    validate_timetable_dates,
)
from app.modules.room.exceptions import RoomNotFoundException
from app.modules.room.models import Room
from app.modules.section_management.exceptions import SectionNotFoundException
from app.modules.section_management.models import Section
from app.modules.subject_management.exceptions import SubjectNotFoundException
from app.modules.subject_management.models import Subject
from app.modules.teacher.exceptions import TeacherNotFoundException
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.exceptions import (
    TeacherSubjectAllocationNotFoundException,
)
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
)
from app.modules.term.exceptions import TermNotFoundException
from app.modules.term.models import Term
from app.modules.time_slot.exceptions import TimeSlotNotFoundException
from app.modules.time_slot.models import TimeSlot


class ClassTimetableService:
    """
    Service class orchestrating Class Timetable configurations, scheduling entries,
    cloning setups, conflict validations, and cache management.
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: ClassTimetableRepository | None = None,
        cache: CacheService | None = None,
        audit: AuditLogService | None = None,
    ) -> None:
        self.db = db
        self.repo = repo or ClassTimetableRepository(db)
        self.cache = cache or CacheService()
        self.audit = audit or AuditLogService(db)

    async def _clear_caches(self, school_id: uuid.UUID) -> None:
        await self.cache.delete_pattern(f"timetable:list:{school_id}:*")
        await self.cache.delete_pattern(f"timetable:weekly:{school_id}:*")
        await self.cache.delete_pattern(f"timetable:published:{school_id}:*")

    # --- Timetable Logic ---
    async def get_timetable(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> ClassTimetable:
        timetable = await self.repo.get_timetable(id, school_id)
        if not timetable:
            raise ClassTimetableNotFoundException()
        return timetable

    async def create_timetable(
        self, school_id: uuid.UUID, data: ClassTimetableCreate, actor: User
    ) -> ClassTimetable:
        validate_timetable_dates(data.effective_from, data.effective_to)

        # Verify entity existences
        await self._verify_timetable_entities(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
        )

        # Get max version
        max_v = await self.repo.get_max_version(
            class_id=data.class_id,
            section_id=data.section_id,
            term_id=data.term_id,
            school_id=school_id,
        )

        timetable = ClassTimetable(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            name=data.name,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            version=max_v + 1,
            status=data.status,
            remarks=data.remarks,
            is_locked=False,
            created_by=actor.id,
            updated_by=actor.id,
        )

        await self.repo.save_timetable(timetable)
        await self.db.flush()
        await self.db.refresh(timetable)

        # Create RecurringSchedule mapping
        recurring = RecurringSchedule(
            school_id=school_id,
            timetable_id=timetable.id,
            day_of_week=DayOfWeek.MONDAY,  # default
            recurrence_pattern="WEEKLY",
        )
        await self.repo.save_recurring_schedule(recurring)

        if timetable.status == TimetableStatus.PUBLISHED:
            await self._handle_publish_overrides(timetable, actor)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="timetable.create",
            entity_name="ClassTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    async def update_timetable(
        self,
        id: uuid.UUID,
        school_id: uuid.UUID,
        data: ClassTimetableUpdate,
        actor: User,
    ) -> ClassTimetable:
        timetable = await self.get_timetable(id, school_id)
        if timetable.is_locked:
            raise TimetableLockedException()

        if data.effective_from is not None or data.effective_to is not None:
            eff_from = (
                data.effective_from
                if data.effective_from is not None
                else timetable.effective_from
            )
            eff_to = (
                data.effective_to
                if data.effective_to is not None
                else timetable.effective_to
            )
            validate_timetable_dates(eff_from, eff_to)
            timetable.effective_from = eff_from
            timetable.effective_to = eff_to

        if data.name is not None:
            timetable.name = data.name
        if data.remarks is not None:
            timetable.remarks = data.remarks
        if data.is_active is not None:
            timetable.is_active = data.is_active

        # Status transition
        if data.status is not None and data.status != timetable.status:
            timetable.status = data.status
            if data.status == TimetableStatus.PUBLISHED:
                await self._handle_publish_overrides(timetable, actor)

        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)
        await self.db.flush()
        await self.db.refresh(timetable)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="timetable.update",
            entity_name="ClassTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    async def delete_timetable(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        timetable = await self.get_timetable(id, school_id)
        if timetable.is_locked:
            raise TimetableLockedException()

        timetable.is_deleted = True
        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)

        # Soft delete entries
        entries = await self.repo.get_weekly_timetable(timetable.id, school_id)
        for entry in entries:
            entry.is_deleted = True
            await self.repo.save_timetable_entry(entry)

        await self.db.flush()
        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="timetable.delete",
            entity_name="ClassTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # --- Timetable Entry Logic ---
    async def get_entry(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> ClassTimetableEntry:
        entry = await self.repo.get_timetable_entry(id, school_id)
        if not entry:
            raise ClassTimetableEntryNotFoundException()
        return entry

    async def add_timetable_entry(
        self, school_id: uuid.UUID, data: ClassTimetableEntryCreate, actor: User
    ) -> ClassTimetableEntry:
        timetable = await self.get_timetable(data.timetable_id, school_id)
        if timetable.is_locked:
            raise TimetableLockedException()

        # Retrieve referenced entities & validate slot
        time_slot = await self._verify_entry_entities(
            school_id=school_id,
            working_day_id=data.working_day_id,
            time_slot_id=data.time_slot_id,
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            room_id=data.room_id,
        )
        validate_time_slot_is_teaching(time_slot)

        # Verify Teacher Subject Allocation exists for this setup
        await self._verify_teacher_allocation(
            school_id=school_id,
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            class_id=timetable.class_id,
            section_id=timetable.section_id,
            academic_year_id=timetable.academic_year_id,
            term_id=timetable.term_id,
            allocation_id=data.teacher_subject_allocation_id,
        )

        # Duplicate check on period slot
        dup_stmt = select(ClassTimetableEntry).where(
            ClassTimetableEntry.timetable_id == data.timetable_id,
            ClassTimetableEntry.working_day_id == data.working_day_id,
            ClassTimetableEntry.time_slot_id == data.time_slot_id,
            ClassTimetableEntry.is_deleted == False,
        )
        if (await self.db.execute(dup_stmt)).scalar_one_or_none():
            raise DuplicateTimetableEntryException()

        # Conflict checks (only if timetable is published)
        if timetable.status == TimetableStatus.PUBLISHED:
            if data.room_id:
                if await self.repo.check_room_conflict(
                    data.room_id, data.working_day_id, data.time_slot_id, school_id
                ):
                    raise RoomNotAvailableException()
            if await self.repo.check_teacher_conflict(
                data.teacher_id, data.working_day_id, data.time_slot_id, school_id
            ):
                raise TeacherNotAvailableException()

        entry = ClassTimetableEntry(
            school_id=school_id,
            timetable_id=data.timetable_id,
            working_day_id=data.working_day_id,
            time_slot_id=data.time_slot_id,
            teacher_subject_allocation_id=data.teacher_subject_allocation_id,
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            room_id=data.room_id,
            period_number=data.period_number,
            lesson_type=data.lesson_type,
            remarks=data.remarks,
        )

        await self.repo.save_timetable_entry(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="entry.create",
            entity_name="ClassTimetableEntry",
            entity_id=entry.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return entry

    async def update_timetable_entry(
        self,
        id: uuid.UUID,
        school_id: uuid.UUID,
        data: ClassTimetableEntryUpdate,
        actor: User,
    ) -> ClassTimetableEntry:
        entry = await self.get_entry(id, school_id)
        timetable = await self.get_timetable(entry.timetable_id, school_id)
        if timetable.is_locked:
            raise TimetableLockedException()

        # Compile targets
        working_day_id = (
            data.working_day_id
            if data.working_day_id is not None
            else entry.working_day_id
        )
        time_slot_id = (
            data.time_slot_id if data.time_slot_id is not None else entry.time_slot_id
        )
        teacher_id = (
            data.teacher_id if data.teacher_id is not None else entry.teacher_id
        )
        subject_id = (
            data.subject_id if data.subject_id is not None else entry.subject_id
        )
        room_id = data.room_id if data.room_id is not None else entry.room_id
        alloc_id = (
            data.teacher_subject_allocation_id
            if data.teacher_subject_allocation_id is not None
            else entry.teacher_subject_allocation_id
        )

        # Verify referenced entities & slot type
        time_slot = await self._verify_entry_entities(
            school_id=school_id,
            working_day_id=working_day_id,
            time_slot_id=time_slot_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
            room_id=room_id,
        )
        validate_time_slot_is_teaching(time_slot)

        # Verify allocation
        await self._verify_teacher_allocation(
            school_id=school_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
            class_id=timetable.class_id,
            section_id=timetable.section_id,
            academic_year_id=timetable.academic_year_id,
            term_id=timetable.term_id,
            allocation_id=alloc_id,
        )

        # Duplicate check on period slot
        if data.working_day_id is not None or data.time_slot_id is not None:
            dup_stmt = select(ClassTimetableEntry).where(
                ClassTimetableEntry.timetable_id == entry.timetable_id,
                ClassTimetableEntry.working_day_id == working_day_id,
                ClassTimetableEntry.time_slot_id == time_slot_id,
                ClassTimetableEntry.id != entry.id,
                ClassTimetableEntry.is_deleted == False,
            )
            if (await self.db.execute(dup_stmt)).scalar_one_or_none():
                raise DuplicateTimetableEntryException()

        # Conflict checks (only if timetable is published)
        if timetable.status == TimetableStatus.PUBLISHED:
            if room_id:
                if await self.repo.check_room_conflict(
                    room_id,
                    working_day_id,
                    time_slot_id,
                    school_id,
                    exclude_entry_id=entry.id,
                ):
                    raise RoomNotAvailableException()
            if await self.repo.check_teacher_conflict(
                teacher_id,
                working_day_id,
                time_slot_id,
                school_id,
                exclude_entry_id=entry.id,
            ):
                raise TeacherNotAvailableException()

        # Update values
        entry.working_day_id = working_day_id
        entry.time_slot_id = time_slot_id
        entry.teacher_id = teacher_id
        entry.subject_id = subject_id
        entry.room_id = room_id
        entry.teacher_subject_allocation_id = alloc_id

        if data.period_number is not None:
            entry.period_number = data.period_number
        if data.lesson_type is not None:
            entry.lesson_type = data.lesson_type
        if data.remarks is not None:
            entry.remarks = data.remarks

        await self.repo.save_timetable_entry(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="entry.update",
            entity_name="ClassTimetableEntry",
            entity_id=entry.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return entry

    async def remove_timetable_entry(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        entry = await self.get_entry(id, school_id)
        timetable = await self.get_timetable(entry.timetable_id, school_id)
        if timetable.is_locked:
            raise TimetableLockedException()

        entry.is_deleted = True
        await self.repo.save_timetable_entry(entry)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="entry.delete",
            entity_name="ClassTimetableEntry",
            entity_id=entry.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # --- Timetable Clone, Publish, Archive Actions ---
    async def clone_timetable(
        self,
        timetable_id: uuid.UUID,
        school_id: uuid.UUID,
        clone_data: TimetableCloneRequest,
        actor: User,
    ) -> ClassTimetable:
        orig = await self.get_timetable(timetable_id, school_id)

        # Verify target existences
        await self._verify_timetable_entities(
            school_id=school_id,
            academic_year_id=orig.academic_year_id,
            term_id=clone_data.target_term_id,
            class_id=clone_data.target_class_id,
            section_id=clone_data.target_section_id,
        )

        max_v = await self.repo.get_max_version(
            class_id=clone_data.target_class_id,
            section_id=clone_data.target_section_id,
            term_id=clone_data.target_term_id,
            school_id=school_id,
        )

        name = clone_data.new_name or f"{orig.name} (Copy)"
        cloned = ClassTimetable(
            school_id=school_id,
            academic_year_id=orig.academic_year_id,
            term_id=clone_data.target_term_id,
            class_id=clone_data.target_class_id,
            section_id=clone_data.target_section_id,
            name=name,
            effective_from=orig.effective_from,
            effective_to=orig.effective_to,
            version=max_v + 1,
            status=TimetableStatus.DRAFT,  # always clones as Draft
            remarks=orig.remarks,
            is_locked=False,
            created_by=actor.id,
            updated_by=actor.id,
        )

        await self.repo.save_timetable(cloned)
        await self.db.flush()
        await self.db.refresh(cloned)

        # Clone RecurringSchedule
        recurring = RecurringSchedule(
            school_id=school_id,
            timetable_id=cloned.id,
            day_of_week=DayOfWeek.MONDAY,
            recurrence_pattern="WEEKLY",
        )
        await self.repo.save_recurring_schedule(recurring)

        # Clone Entries
        orig_entries = await self.repo.get_weekly_timetable(orig.id, school_id)
        for oe in orig_entries:
            # We map teacher_subject_allocation recursively if possible, or fallback
            # In a clean copy, class subject section might differ, so we resolve allocation
            # by matching details for the target class/section
            target_alloc_id = None
            alloc_stmt = select(TeacherSubjectAllocation).where(
                TeacherSubjectAllocation.school_id == school_id,
                TeacherSubjectAllocation.teacher_id == oe.teacher_id,
                TeacherSubjectAllocation.subject_id == oe.subject_id,
                TeacherSubjectAllocation.class_id == clone_data.target_class_id,
                TeacherSubjectAllocation.section_id == clone_data.target_section_id,
                TeacherSubjectAllocation.is_deleted == False,
            )
            alloc_obj = (await self.db.execute(alloc_stmt)).scalar_one_or_none()
            if alloc_obj:
                target_alloc_id = alloc_obj.id

            ce = ClassTimetableEntry(
                school_id=school_id,
                timetable_id=cloned.id,
                working_day_id=oe.working_day_id,
                time_slot_id=oe.time_slot_id,
                teacher_subject_allocation_id=target_alloc_id,
                teacher_id=oe.teacher_id,
                subject_id=oe.subject_id,
                room_id=oe.room_id,
                period_number=oe.period_number,
                lesson_type=oe.lesson_type,
                remarks=oe.remarks,
            )
            await self.repo.save_timetable_entry(ce)

        await self.db.flush()
        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="timetable.clone",
            entity_name="ClassTimetable",
            entity_id=cloned.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return cloned

    async def publish_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> ClassTimetable:
        timetable = await self.get_timetable(timetable_id, school_id)
        if timetable.status == TimetableStatus.PUBLISHED:
            return timetable

        timetable.status = TimetableStatus.PUBLISHED
        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)

        # Run overrides
        await self._handle_publish_overrides(timetable, actor)

        await self.db.flush()
        await self.db.refresh(timetable)
        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="timetable.publish",
            entity_name="ClassTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    async def archive_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> ClassTimetable:
        timetable = await self.get_timetable(timetable_id, school_id)
        if timetable.status == TimetableStatus.ARCHIVED:
            return timetable

        timetable.status = TimetableStatus.ARCHIVED
        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)

        await self.db.flush()
        await self.db.refresh(timetable)
        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="class_timetable",
            action="timetable.archive",
            entity_name="ClassTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    # --- Weekly grid generation ---
    async def generate_weekly_schedule(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID
    ) -> WeeklyScheduleResponse:
        # Check cache
        cache_key = f"timetable:weekly:{school_id}:{timetable_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return WeeklyScheduleResponse.model_validate(cached)

        timetable = await self.get_timetable(timetable_id, school_id)
        entries = await self.repo.get_weekly_timetable(timetable_id, school_id)

        # Query all working days of the school academic year
        wd_stmt = (
            select(WorkingDay)
            .where(
                WorkingDay.academic_year_id == timetable.academic_year_id,
                WorkingDay.school_id == school_id,
                WorkingDay.is_deleted == False,
            )
            .order_by(WorkingDay.display_order.asc())
        )
        working_days = (await self.db.execute(wd_stmt)).scalars().all()

        schedule = []
        for wd in working_days:
            wd_entries = [e for e in entries if e.working_day_id == wd.id]
            cell_summaries = []
            for e in wd_entries:
                subject_name = e.subject.subject_name
                # Teacher name resolution
                teacher_emp = e.teacher.employee
                teacher_name = f"{teacher_emp.first_name} {teacher_emp.last_name}"
                room_name = e.room.room_name if e.room else None

                cell_summaries.append(
                    TimetableEntrySummary(
                        entry_id=e.id,
                        period_number=e.period_number,
                        lesson_type=e.lesson_type,
                        subject_id=e.subject_id,
                        subject_name=subject_name,
                        teacher_id=e.teacher_id,
                        teacher_name=teacher_name,
                        room_id=e.room_id,
                        room_name=room_name,
                        remarks=e.remarks,
                    )
                )

            schedule.append(
                DayScheduleSummary(
                    working_day_id=wd.id,
                    day_of_week=wd.day_of_week.value,
                    is_working=wd.is_working,
                    entries=cell_summaries,
                )
            )

        resp = WeeklyScheduleResponse(
            timetable_id=timetable.id,
            class_id=timetable.class_id,
            section_id=timetable.section_id,
            term_id=timetable.term_id,
            academic_year_id=timetable.academic_year_id,
            name=timetable.name,
            status=timetable.status,
            version=timetable.version,
            schedule=schedule,
        )

        # Store in Redis
        await self.cache.set(cache_key, resp.model_dump(mode="json"), ttl=3600)
        return resp

    # --- Helper methods ---
    async def _handle_publish_overrides(
        self, timetable: ClassTimetable, actor: User
    ) -> None:
        # Locate other published timetables for the same class+section+term
        stmt = select(ClassTimetable).where(
            ClassTimetable.class_id == timetable.class_id,
            ClassTimetable.section_id == timetable.section_id,
            ClassTimetable.term_id == timetable.term_id,
            ClassTimetable.school_id == timetable.school_id,
            ClassTimetable.status == TimetableStatus.PUBLISHED,
            ClassTimetable.id != timetable.id,
            ClassTimetable.is_deleted == False,
        )
        others = (await self.db.execute(stmt)).scalars().all()
        for other in others:
            other.status = TimetableStatus.ARCHIVED
            other.updated_by = actor.id
            await self.repo.save_timetable(other)

    async def _verify_timetable_entities(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
    ) -> None:
        # Academic Year
        ay_stmt = select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
        )
        if not (await self.db.execute(ay_stmt)).scalar_one_or_none():
            raise AcademicYearNotFoundException()

        # Term
        t_stmt = select(Term).where(
            Term.id == term_id, Term.school_id == school_id, Term.is_deleted == False
        )
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TermNotFoundException()

        # Class
        c_stmt = select(SchoolClass).where(
            SchoolClass.id == class_id,
            SchoolClass.school_id == school_id,
            SchoolClass.is_deleted == False,
        )
        if not (await self.db.execute(c_stmt)).scalar_one_or_none():
            raise NotFoundException("Class not found.")

        # Section
        s_stmt = select(Section).where(
            Section.id == section_id,
            Section.school_id == school_id,
            Section.is_deleted == False,
        )
        if not (await self.db.execute(s_stmt)).scalar_one_or_none():
            raise SectionNotFoundException()

    async def _verify_entry_entities(
        self,
        school_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        teacher_id: uuid.UUID,
        subject_id: uuid.UUID,
        room_id: uuid.UUID | None = None,
    ) -> TimeSlot:
        # Working Day
        wd_stmt = select(WorkingDay).where(
            WorkingDay.id == working_day_id,
            WorkingDay.school_id == school_id,
            WorkingDay.is_deleted == False,
        )
        if not (await self.db.execute(wd_stmt)).scalar_one_or_none():
            raise NotFoundException("Working day not found.")

        # Time Slot
        ts_stmt = select(TimeSlot).where(
            TimeSlot.id == time_slot_id,
            TimeSlot.school_id == school_id,
            TimeSlot.is_deleted == False,
        )
        time_slot = (await self.db.execute(ts_stmt)).scalar_one_or_none()
        if not time_slot:
            raise TimeSlotNotFoundException()

        # Teacher
        t_stmt = select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.school_id == school_id,
            Teacher.is_deleted == False,
        )
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TeacherNotFoundException()

        # Subject
        sub_stmt = select(Subject).where(
            Subject.id == subject_id,
            Subject.school_id == school_id,
            Subject.is_deleted == False,
        )
        if not (await self.db.execute(sub_stmt)).scalar_one_or_none():
            raise SubjectNotFoundException()

        # Room (optional)
        if room_id:
            r_stmt = select(Room).where(
                Room.id == room_id,
                Room.school_id == school_id,
                Room.is_deleted == False,
            )
            if not (await self.db.execute(r_stmt)).scalar_one_or_none():
                raise RoomNotFoundException()

        return time_slot

    async def _verify_teacher_allocation(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        subject_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        allocation_id: uuid.UUID | None = None,
    ) -> None:
        if allocation_id:
            stmt = select(TeacherSubjectAllocation).where(
                TeacherSubjectAllocation.id == allocation_id,
                TeacherSubjectAllocation.school_id == school_id,
                TeacherSubjectAllocation.teacher_id == teacher_id,
                TeacherSubjectAllocation.subject_id == subject_id,
                TeacherSubjectAllocation.class_id == class_id,
                TeacherSubjectAllocation.section_id == section_id,
                TeacherSubjectAllocation.academic_year_id == academic_year_id,
                TeacherSubjectAllocation.term_id == term_id,
                TeacherSubjectAllocation.is_deleted == False,
            )
            if not (await self.db.execute(stmt)).scalar_one_or_none():
                raise TeacherSubjectAllocationNotFoundException()
        else:
            stmt = select(TeacherSubjectAllocation).where(
                TeacherSubjectAllocation.school_id == school_id,
                TeacherSubjectAllocation.teacher_id == teacher_id,
                TeacherSubjectAllocation.subject_id == subject_id,
                TeacherSubjectAllocation.class_id == class_id,
                TeacherSubjectAllocation.section_id == section_id,
                TeacherSubjectAllocation.academic_year_id == academic_year_id,
                TeacherSubjectAllocation.term_id == term_id,
                TeacherSubjectAllocation.is_deleted == False,
            )
            if not (await self.db.execute(stmt)).scalar_one_or_none():
                raise TeacherSubjectAllocationNotFoundException(
                    detail="Teacher does not hold active subject section allocation."
                )
