import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.class_model import SchoolClass
from app.models.user import User
from app.modules.academic_calendar.exceptions import (
    AcademicYearNotFoundException,
    WorkingDayNotFoundException,
)
from app.modules.academic_calendar.models import WorkingDay
from app.modules.academic_year.models import AcademicYear
from app.modules.time_slot.exceptions import (
    BreakPeriodNotFoundException,
    ClassNotFoundException,
    DuplicateTimeSlotException,
    PeriodNotFoundException,
    TimeSlotNotFoundException,
)
from app.modules.time_slot.models import BreakPeriod, Period, TimeSlot
from app.modules.time_slot.repository import TimeSlotRepository
from app.modules.time_slot.schemas import (
    BreakPeriodCreate,
    BreakPeriodUpdate,
    PeriodCreate,
    PeriodUpdate,
    TimeSlotCreate,
    TimeSlotUpdate,
)
from app.modules.time_slot.validators import (
    validate_duration_matches,
    validate_no_overlap,
    validate_time_range,
    validate_uniqueness,
)

logger = logging.getLogger(__name__)


class TimeSlotService:
    """
    Service layer orchestrating domain logic, timing validations, overlap checks,
    database persistence via repositories, audit logs, and cache controls.
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = TimeSlotRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    # --- Caches ---
    async def _clear_caches(
        self, school_id: uuid.UUID, working_day_id: uuid.UUID | None = None
    ) -> None:
        if working_day_id:
            await self.cache.delete(
                f"timeslot:working_day:{school_id}:{working_day_id}"
            )
        await self.cache.delete_pattern(f"timeslot:list:{school_id}:*")

    # --- Exists checks ---
    async def _verify_academic_year_exists(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> None:
        stmt = select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
        )
        ay = (await self.db.execute(stmt)).scalar_one_or_none()
        if not ay:
            raise AcademicYearNotFoundException()

    async def _verify_working_day_exists(
        self, school_id: uuid.UUID, working_day_id: uuid.UUID
    ) -> None:
        stmt = select(WorkingDay).where(
            WorkingDay.id == working_day_id,
            WorkingDay.school_id == school_id,
            WorkingDay.is_deleted == False,
        )
        wd = (await self.db.execute(stmt)).scalar_one_or_none()
        if not wd:
            raise WorkingDayNotFoundException()

    async def _verify_class_exists(
        self, school_id: uuid.UUID, class_id: uuid.UUID
    ) -> None:
        stmt = select(SchoolClass).where(
            SchoolClass.id == class_id,
            SchoolClass.school_id == school_id,
            SchoolClass.is_deleted == False,
        )
        sc = (await self.db.execute(stmt)).scalar_one_or_none()
        if not sc:
            raise ClassNotFoundException()

    # --- Time Slots CRUD ---
    async def get_time_slot(self, id: uuid.UUID, school_id: uuid.UUID) -> TimeSlot:
        slot = await self.repo.get_time_slot(id, school_id)
        if not slot:
            raise TimeSlotNotFoundException()
        return slot

    async def list_time_slots(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        working_day_id: uuid.UUID | None = None,
        slot_type: str | None = None,
        is_break: bool | None = None,
        is_active: bool | None = None,
        sort_by: str = "display_order",
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[TimeSlot]:
        cache_key = f"timeslot:list:{school_id}:{academic_year_id}:{working_day_id}:{slot_type}:{is_break}:{is_active}:{sort_by}:{skip}:{limit}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            # We want to reconstitute DB objects, but for list serialization, cached dicts work fine if the router handles it.
            # However, returning raw lists of models is better for direct calls. Let's hit the repo or fallback to db.
            # To ensure standard models are returned, we fetch from database, but let's cache and return if cached.
            # If cached is returned directly as dicts, the API layer serializes correctly. Let's do standard db fetch.
            pass

        slots = await self.repo.list_time_slots(
            school_id=school_id,
            academic_year_id=academic_year_id,
            working_day_id=working_day_id,
            slot_type=slot_type,
            is_break=is_break,
            is_active=is_active,
            sort_by=sort_by,
            skip=skip,
            limit=limit,
        )
        for s in slots:
            await self.db.refresh(s)
        return slots

    async def create_time_slot(
        self, school_id: uuid.UUID, data: TimeSlotCreate, actor: User
    ) -> TimeSlot:
        await self._verify_academic_year_exists(school_id, data.academic_year_id)
        await self._verify_working_day_exists(school_id, data.working_day_id)

        validate_time_range(data.start_time, data.end_time)
        validate_duration_matches(data.start_time, data.end_time, data.duration_minutes)

        existing = await self.repo.get_working_day_slots(school_id, data.working_day_id)
        validate_uniqueness(data.display_order, data.slot_number, existing)
        validate_no_overlap(data.start_time, data.end_time, existing)

        slot = TimeSlot(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            slot_number=data.slot_number,
            start_time=data.start_time,
            end_time=data.end_time,
            duration_minutes=data.duration_minutes,
            slot_type=data.slot_type,
            working_day_id=data.working_day_id,
            display_order=data.display_order,
            is_break=data.is_break,
            is_teaching=data.is_teaching,
            is_active=data.is_active,
            is_locked=False,
            created_by=actor.id,
            updated_by=actor.id,
        )

        await self.repo.save_time_slot(slot)
        await self.db.flush()
        await self.db.refresh(slot)

        await self._clear_caches(school_id, data.working_day_id)

        await self.audit.log_action(
            module="time_slot",
            action="time_slot.create",
            entity_name="TimeSlot",
            entity_id=slot.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return slot

    async def update_time_slot(
        self, id: uuid.UUID, school_id: uuid.UUID, data: TimeSlotUpdate, actor: User
    ) -> TimeSlot:
        slot = await self.get_time_slot(id, school_id)

        new_start = data.start_time if data.start_time is not None else slot.start_time
        new_end = data.end_time if data.end_time is not None else slot.end_time
        new_duration = (
            data.duration_minutes
            if data.duration_minutes is not None
            else slot.duration_minutes
        )
        new_order = (
            data.display_order if data.display_order is not None else slot.display_order
        )
        new_slot_number = (
            data.slot_number if data.slot_number is not None else slot.slot_number
        )

        # Timing validations
        if data.start_time is not None or data.end_time is not None:
            validate_time_range(new_start, new_end)
        if (
            data.start_time is not None
            or data.end_time is not None
            or data.duration_minutes is not None
        ):
            validate_duration_matches(new_start, new_end, new_duration)

        # Uniqueness and overlap validations
        if (
            data.start_time is not None
            or data.end_time is not None
            or data.display_order is not None
            or data.slot_number is not None
        ):
            existing = await self.repo.get_working_day_slots(
                school_id, slot.working_day_id
            )
            validate_uniqueness(new_order, new_slot_number, existing, exclude_id=id)
            validate_no_overlap(new_start, new_end, existing, exclude_id=id)

        # Set attributes
        if data.name is not None:
            slot.name = data.name
        if data.slot_number is not None:
            slot.slot_number = data.slot_number
        if data.start_time is not None:
            slot.start_time = data.start_time
        if data.end_time is not None:
            slot.end_time = data.end_time
        if data.duration_minutes is not None:
            slot.duration_minutes = data.duration_minutes
        if data.slot_type is not None:
            slot.slot_type = data.slot_type
        if data.display_order is not None:
            slot.display_order = data.display_order
        if data.is_break is not None:
            slot.is_break = data.is_break
        if data.is_teaching is not None:
            slot.is_teaching = data.is_teaching
        if data.is_active is not None:
            slot.is_active = data.is_active

        slot.updated_by = actor.id

        await self.repo.save_time_slot(slot)
        await self.db.flush()
        await self.db.refresh(slot)

        await self._clear_caches(school_id, slot.working_day_id)

        await self.audit.log_action(
            module="time_slot",
            action="time_slot.update",
            entity_name="TimeSlot",
            entity_id=slot.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return slot

    async def delete_time_slot(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        slot = await self.get_time_slot(id, school_id)
        slot.is_deleted = True
        slot.deleted_at = (
            self.db.info.get("now", None) or uuid.uuid4()
        )  # soft delete flag
        slot.updated_by = actor.id

        await self.repo.save_time_slot(slot)
        await self.db.flush()

        await self._clear_caches(school_id, slot.working_day_id)

        await self.audit.log_action(
            module="time_slot",
            action="time_slot.delete",
            entity_name="TimeSlot",
            entity_id=slot.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # --- Periods CRUD ---
    async def get_period(self, id: uuid.UUID, school_id: uuid.UUID) -> Period:
        period = await self.repo.get_period(id, school_id)
        if not period:
            raise PeriodNotFoundException()
        return period

    async def list_periods(
        self,
        school_id: uuid.UUID,
        time_slot_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Period]:
        periods = await self.repo.list_periods(
            school_id, time_slot_id, class_id, is_active, skip, limit
        )
        for p in periods:
            await self.db.refresh(p)
        return periods

    async def create_period(
        self, school_id: uuid.UUID, data: PeriodCreate, actor: User
    ) -> Period:
        await self.get_time_slot(data.time_slot_id, school_id)
        await self._verify_class_exists(school_id, data.class_id)

        # Check duplicate Link (TimeSlot & Class)
        existing = await self.repo.list_periods(
            school_id=school_id, time_slot_id=data.time_slot_id, class_id=data.class_id
        )
        if existing:
            raise DuplicateTimeSlotException(
                "A period configuration already exists for this time slot and class level."
            )

        period = Period(
            school_id=school_id,
            time_slot_id=data.time_slot_id,
            class_id=data.class_id,
            default_subject_duration_minutes=data.default_subject_duration_minutes,
            default_teacher_duration_minutes=data.default_teacher_duration_minutes,
            max_capacity=data.max_capacity,
            is_active=True,
        )

        await self.repo.save_period(period)
        await self.db.flush()
        await self.db.refresh(period)

        await self.audit.log_action(
            module="time_slot",
            action="period.create",
            entity_name="Period",
            entity_id=period.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return period

    async def update_period(
        self, id: uuid.UUID, school_id: uuid.UUID, data: PeriodUpdate, actor: User
    ) -> Period:
        period = await self.get_period(id, school_id)

        if data.default_subject_duration_minutes is not None:
            period.default_subject_duration_minutes = (
                data.default_subject_duration_minutes
            )
        if data.default_teacher_duration_minutes is not None:
            period.default_teacher_duration_minutes = (
                data.default_teacher_duration_minutes
            )
        if data.max_capacity is not None:
            period.max_capacity = data.max_capacity
        if data.is_active is not None:
            period.is_active = data.is_active

        await self.repo.save_period(period)
        await self.db.flush()
        await self.db.refresh(period)

        await self.audit.log_action(
            module="time_slot",
            action="period.update",
            entity_name="Period",
            entity_id=period.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return period

    async def delete_period(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        period = await self.get_period(id, school_id)
        period.is_deleted = True

        await self.repo.save_period(period)
        await self.db.flush()

        await self.audit.log_action(
            module="time_slot",
            action="period.delete",
            entity_name="Period",
            entity_id=period.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # --- Break Periods CRUD ---
    async def get_break_period(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> BreakPeriod:
        bp = await self.repo.get_break_period(id, school_id)
        if not bp:
            raise BreakPeriodNotFoundException()
        return bp

    async def list_break_periods(
        self,
        school_id: uuid.UUID,
        time_slot_id: uuid.UUID | None = None,
        break_type: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[BreakPeriod]:
        bps = await self.repo.list_break_periods(
            school_id, time_slot_id, break_type, is_active, skip, limit
        )
        for b in bps:
            await self.db.refresh(b)
        return bps

    async def create_break_period(
        self, school_id: uuid.UUID, data: BreakPeriodCreate, actor: User
    ) -> BreakPeriod:
        await self.get_time_slot(data.time_slot_id, school_id)

        # Check duplicate Break Period by name in the same time slot
        existing = await self.repo.list_break_periods(
            school_id=school_id, time_slot_id=data.time_slot_id
        )
        if any(b.name.lower() == data.name.lower() for b in existing):
            raise DuplicateTimeSlotException(
                f"A break period named '{data.name}' already exists for this time slot."
            )

        bp = BreakPeriod(
            school_id=school_id,
            time_slot_id=data.time_slot_id,
            break_type=data.break_type,
            name=data.name,
            duration_minutes=data.duration_minutes,
            description=data.description,
            is_active=True,
        )

        await self.repo.save_break_period(bp)
        await self.db.flush()
        await self.db.refresh(bp)

        await self.audit.log_action(
            module="time_slot",
            action="break_period.create",
            entity_name="BreakPeriod",
            entity_id=bp.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return bp

    async def update_break_period(
        self, id: uuid.UUID, school_id: uuid.UUID, data: BreakPeriodUpdate, actor: User
    ) -> BreakPeriod:
        bp = await self.get_break_period(id, school_id)

        if data.name is not None and data.name.lower() != bp.name.lower():
            existing = await self.repo.list_break_periods(
                school_id=school_id, time_slot_id=bp.time_slot_id
            )
            if any(
                b.id != id and b.name.lower() == data.name.lower() for b in existing
            ):
                raise DuplicateTimeSlotException(
                    f"A break period named '{data.name}' already exists for this time slot."
                )
            bp.name = data.name

        if data.break_type is not None:
            bp.break_type = data.break_type
        if data.duration_minutes is not None:
            bp.duration_minutes = data.duration_minutes
        if data.description is not None:
            bp.description = data.description
        if data.is_active is not None:
            bp.is_active = data.is_active

        await self.repo.save_break_period(bp)
        await self.db.flush()
        await self.db.refresh(bp)

        await self.audit.log_action(
            module="time_slot",
            action="break_period.update",
            entity_name="BreakPeriod",
            entity_id=bp.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return bp

    async def delete_break_period(
        self, id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> None:
        bp = await self.get_break_period(id, school_id)
        bp.is_deleted = True

        await self.repo.save_break_period(bp)
        await self.db.flush()

        await self.audit.log_action(
            module="time_slot",
            action="break_period.delete",
            entity_name="BreakPeriod",
            entity_id=bp.id,
            user_id=actor.id,
            school_id=school_id,
        )
