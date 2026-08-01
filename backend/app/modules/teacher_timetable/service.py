import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.exceptions.exceptions import NotFoundException
from app.models.user import User
from app.modules.academic_calendar.models import WorkingDay
from app.modules.academic_year.exceptions import AcademicYearNotFoundException
from app.modules.academic_year.models import AcademicYear
from app.modules.teacher.exceptions import TeacherNotFoundException
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import TeacherWorkload
from app.modules.teacher_timetable.enums import (
    TeacherAvailabilityStatus,
    TeacherTimetableStatus,
)
from app.modules.teacher_timetable.exceptions import (
    OverlappingPeriodException,
    TeacherAvailabilityNotFoundException,
    TeacherTimetableLockedException,
    TeacherTimetableNotFoundException,
    TeacherUnavailableException,
    WorkloadLimitExceededException,
)
from app.modules.teacher_timetable.models import (
    TeacherAvailability,
    TeacherTimetable,
    TeacherTimetableEntry,
)
from app.modules.teacher_timetable.repository import TeacherTimetableRepository
from app.modules.teacher_timetable.schemas import (
    TeacherAvailabilityCreate,
    TeacherAvailabilitySummary,
    TeacherDayScheduleSummary,
    TeacherTimetableCreate,
    TeacherTimetableEntrySummary,
    TeacherTimetableUpdate,
    TeacherWeeklyScheduleResponse,
)
from app.modules.teacher_timetable.validators import validate_timetable_dates
from app.modules.term.exceptions import TermNotFoundException
from app.modules.term.models import Term
from app.modules.time_slot.exceptions import TimeSlotNotFoundException
from app.modules.time_slot.models import TimeSlot


class TeacherTimetableService:
    """
    Service class orchestrating teacher timetables, entries, custom availability,
    synchronization from class schedules, and validation constraints.
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: TeacherTimetableRepository | None = None,
        cache: CacheService | None = None,
        audit: AuditLogService | None = None,
    ) -> None:
        self.db = db
        self.repo = repo or TeacherTimetableRepository(db)
        self.cache = cache or CacheService()
        self.audit = audit or AuditLogService(db)

    async def _clear_caches(self, school_id: uuid.UUID) -> None:
        await self.cache.delete_pattern(f"teacher_timetable:list:{school_id}:*")
        await self.cache.delete_pattern(f"teacher_timetable:weekly:{school_id}:*")
        await self.cache.delete_pattern(f"teacher_timetable:availability:{school_id}:*")

    # --- Timetable Logic ---
    async def get_timetable(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherTimetable:
        timetable = await self.repo.get_timetable(id, school_id)
        if not timetable:
            raise TeacherTimetableNotFoundException()
        return timetable

    async def create_timetable(
        self, school_id: uuid.UUID, data: TeacherTimetableCreate, actor: User
    ) -> TeacherTimetable:
        validate_timetable_dates(data.effective_from, data.effective_to)

        # Verify teacher, academic year, and term exist
        await self._verify_timetable_entities(
            school_id=school_id,
            teacher_id=data.teacher_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
        )

        max_v = await self.repo.get_max_version(
            teacher_id=data.teacher_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            school_id=school_id,
        )

        timetable = TeacherTimetable(
            school_id=school_id,
            teacher_id=data.teacher_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
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

        if timetable.status == TeacherTimetableStatus.PUBLISHED:
            await self._handle_publish_overrides(timetable, actor)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_timetable",
            action="timetable.create",
            entity_name="TeacherTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    async def update_timetable(
        self,
        id: uuid.UUID,
        school_id: uuid.UUID,
        data: TeacherTimetableUpdate,
        actor: User,
    ) -> TeacherTimetable:
        timetable = await self.get_timetable(id, school_id)
        if timetable.is_locked:
            raise TeacherTimetableLockedException()

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
            if data.status == TeacherTimetableStatus.PUBLISHED:
                await self._handle_publish_overrides(timetable, actor)

        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)
        await self.db.flush()
        await self.db.refresh(timetable)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_timetable",
            action="timetable.update",
            entity_name="TeacherTimetable",
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
            raise TeacherTimetableLockedException()

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
            module="teacher_timetable",
            action="timetable.delete",
            entity_name="TeacherTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # --- Timetable Synchronisation Logic ---
    async def synchronize_from_class_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> TeacherTimetable:
        timetable = await self.get_timetable(timetable_id, school_id)
        if timetable.is_locked:
            raise TeacherTimetableLockedException()

        # Delete existing entries
        existing_entries = await self.repo.get_weekly_timetable(timetable.id, school_id)
        for entry in existing_entries:
            entry.is_deleted = True
            await self.repo.save_timetable_entry(entry)
        await self.db.flush()

        # Find published ClassTimetableEntry rows for the teacher
        class_entries = await self.repo.find_published_class_entries_for_teacher(
            teacher_id=timetable.teacher_id,
            academic_year_id=timetable.academic_year_id,
            term_id=timetable.term_id,
            school_id=school_id,
        )

        # Workload limit validation check
        workload_stmt = select(TeacherWorkload).where(
            TeacherWorkload.teacher_id == timetable.teacher_id,
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        workload_obj = (await self.db.execute(workload_stmt)).scalar_one_or_none()
        max_periods = (
            workload_obj.maximum_weekly_periods if workload_obj else 24
        )  # sensible default if no limit config exists

        if len(class_entries) > max_periods:
            raise WorkloadLimitExceededException(
                detail=f"Synchronization failed. Total periods ({len(class_entries)}) exceeds maximum workload limit ({max_periods})."
            )

        # Verify overlaps and availability
        seen_slots = set()
        for ce in class_entries:
            slot_key = (ce.working_day_id, ce.time_slot_id)

            # Check duplication within class schedules (overlapping period)
            if slot_key in seen_slots:
                raise OverlappingPeriodException(
                    detail="Overlapping schedule detected in published class timetables."
                )
            seen_slots.add(slot_key)

            # Verify availability
            avail = await self.repo.lookup_availability(
                teacher_id=timetable.teacher_id,
                working_day_id=ce.working_day_id,
                time_slot_id=ce.time_slot_id,
                school_id=school_id,
            )
            if (
                avail
                and avail.availability_status == TeacherAvailabilityStatus.UNAVAILABLE
            ):
                raise TeacherUnavailableException(
                    detail="Teacher is unavailable for a scheduled period in the published class timetable."
                )

            # Create entry replica
            entry = TeacherTimetableEntry(
                school_id=school_id,
                teacher_timetable_id=timetable.id,
                working_day_id=ce.working_day_id,
                time_slot_id=ce.time_slot_id,
                class_timetable_entry_id=ce.id,
                class_id=ce.timetable.class_id,
                section_id=ce.timetable.section_id,
                subject_id=ce.subject_id,
                room_id=ce.room_id,
                lesson_type=ce.lesson_type,
                remarks=ce.remarks,
            )
            await self.repo.save_timetable_entry(entry)

        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)
        await self.db.flush()
        await self.db.refresh(timetable)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_timetable",
            action="timetable.synchronize",
            entity_name="TeacherTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    # --- Custom Availability Logic ---
    async def get_availability(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherAvailability:
        avail = await self.repo.get_availability(id, school_id)
        if not avail:
            raise TeacherAvailabilityNotFoundException()
        return avail

    async def update_availability(
        self, school_id: uuid.UUID, data: TeacherAvailabilityCreate, actor: User
    ) -> TeacherAvailability:
        # Verify teacher, working day, slot exist
        await self._verify_availability_entities(
            school_id=school_id,
            teacher_id=data.teacher_id,
            working_day_id=data.working_day_id,
            time_slot_id=data.time_slot_id,
        )

        # Lookup existing custom availability
        avail = await self.repo.lookup_availability(
            teacher_id=data.teacher_id,
            working_day_id=data.working_day_id,
            time_slot_id=data.time_slot_id,
            school_id=school_id,
        )

        if avail:
            avail.availability_status = data.availability_status
            avail.reason = data.reason
        else:
            avail = TeacherAvailability(
                school_id=school_id,
                teacher_id=data.teacher_id,
                working_day_id=data.working_day_id,
                time_slot_id=data.time_slot_id,
                availability_status=data.availability_status,
                reason=data.reason,
            )

        await self.repo.save_availability(avail)
        await self.db.flush()
        await self.db.refresh(avail)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_timetable",
            action="availability.update",
            entity_name="TeacherAvailability",
            entity_id=avail.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return avail

    # --- Timetable Actions ---
    async def publish_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> TeacherTimetable:
        timetable = await self.get_timetable(timetable_id, school_id)
        if timetable.status == TeacherTimetableStatus.PUBLISHED:
            return timetable

        timetable.status = TeacherTimetableStatus.PUBLISHED
        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)

        # Handle version archival overrides
        await self._handle_publish_overrides(timetable, actor)

        await self.db.flush()
        await self.db.refresh(timetable)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_timetable",
            action="timetable.publish",
            entity_name="TeacherTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    async def archive_timetable(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> TeacherTimetable:
        timetable = await self.get_timetable(timetable_id, school_id)
        if timetable.status == TeacherTimetableStatus.ARCHIVED:
            return timetable

        timetable.status = TeacherTimetableStatus.ARCHIVED
        timetable.updated_by = actor.id
        await self.repo.save_timetable(timetable)

        await self.db.flush()
        await self.db.refresh(timetable)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_timetable",
            action="timetable.archive",
            entity_name="TeacherTimetable",
            entity_id=timetable.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return timetable

    # --- Weekly Schedule Grid Generation ---
    async def generate_weekly_schedule(
        self, timetable_id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherWeeklyScheduleResponse:
        # Check cache
        cache_key = f"teacher_timetable:weekly:{school_id}:{timetable_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return TeacherWeeklyScheduleResponse.model_validate(cached)

        timetable = await self.get_timetable(timetable_id, school_id)
        entries = await self.repo.get_weekly_timetable(timetable_id, school_id)
        availabilities = await self.repo.get_availabilities_by_teacher(
            timetable.teacher_id, school_id
        )

        # Query all working days of the academic year
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
            wd_availabilities = [a for a in availabilities if a.working_day_id == wd.id]

            cell_summaries = []
            for e in wd_entries:
                cell_summaries.append(
                    TeacherTimetableEntrySummary(
                        entry_id=e.id,
                        class_id=e.class_id,
                        class_name=e.school_class.name,
                        section_id=e.section_id,
                        section_name=e.section.name,
                        subject_id=e.subject_id,
                        subject_name=e.subject.subject_name,
                        room_id=e.room_id,
                        room_name=e.room.room_name if e.room else None,
                        lesson_type=e.lesson_type,
                        remarks=e.remarks,
                    )
                )

            avail_summaries = []
            for a in wd_availabilities:
                avail_summaries.append(
                    TeacherAvailabilitySummary(
                        availability_id=a.id,
                        availability_status=a.availability_status,
                        reason=a.reason,
                    )
                )

            schedule.append(
                TeacherDayScheduleSummary(
                    working_day_id=wd.id,
                    day_of_week=wd.day_of_week.value,
                    is_working=wd.is_working,
                    entries=cell_summaries,
                    availabilities=avail_summaries,
                )
            )

        # Teacher name resolution
        teacher_emp = timetable.teacher.employee
        teacher_name = f"{teacher_emp.first_name} {teacher_emp.last_name}"

        resp = TeacherWeeklyScheduleResponse(
            teacher_timetable_id=timetable.id,
            teacher_id=timetable.teacher_id,
            teacher_name=teacher_name,
            academic_year_id=timetable.academic_year_id,
            term_id=timetable.term_id,
            name=timetable.name,
            status=timetable.status,
            version=timetable.version,
            schedule=schedule,
        )

        # Cache locally/Redis
        await self.cache.set(cache_key, resp.model_dump(mode="json"), ttl=3600)
        return resp

    # --- Helper methods ---
    async def _handle_publish_overrides(
        self, timetable: TeacherTimetable, actor: User
    ) -> None:
        stmt = select(TeacherTimetable).where(
            TeacherTimetable.teacher_id == timetable.teacher_id,
            TeacherTimetable.academic_year_id == timetable.academic_year_id,
            TeacherTimetable.term_id == timetable.term_id,
            TeacherTimetable.school_id == timetable.school_id,
            TeacherTimetable.status == TeacherTimetableStatus.PUBLISHED,
            TeacherTimetable.id != timetable.id,
            TeacherTimetable.is_deleted == False,
        )
        others = (await self.db.execute(stmt)).scalars().all()
        for other in others:
            other.status = TeacherTimetableStatus.ARCHIVED
            other.updated_by = actor.id
            await self.repo.save_timetable(other)

    async def _verify_timetable_entities(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> None:
        # Teacher
        t_stmt = select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.school_id == school_id,
            Teacher.is_deleted == False,
        )
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TeacherNotFoundException()

        # Academic Year
        ay_stmt = select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
        )
        if not (await self.db.execute(ay_stmt)).scalar_one_or_none():
            raise AcademicYearNotFoundException()

        # Term
        term_stmt = select(Term).where(
            Term.id == term_id, Term.school_id == school_id, Term.is_deleted == False
        )
        if not (await self.db.execute(term_stmt)).scalar_one_or_none():
            raise TermNotFoundException()

    async def _verify_availability_entities(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
    ) -> None:
        # Teacher
        t_stmt = select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.school_id == school_id,
            Teacher.is_deleted == False,
        )
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TeacherNotFoundException()

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
        if not (await self.db.execute(ts_stmt)).scalar_one_or_none():
            raise TimeSlotNotFoundException()
