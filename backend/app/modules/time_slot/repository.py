import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.time_slot.models import BreakPeriod, Period, TimeSlot


class TimeSlotRepository:
    """
    Repository executing Async SQLAlchemy queries for TimeSlot, Period, and BreakPeriod models.
    Supports complete CRUD operations, tenant isolation, dynamic filters, sorting, and pagination.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Time Slots ---
    async def get_time_slot(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> TimeSlot | None:
        stmt = select(TimeSlot).where(
            TimeSlot.id == id,
            TimeSlot.school_id == school_id,
            TimeSlot.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

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
        stmt = select(TimeSlot).where(
            TimeSlot.school_id == school_id,
            TimeSlot.is_deleted == False,
        )

        if academic_year_id is not None:
            stmt = stmt.where(TimeSlot.academic_year_id == academic_year_id)
        if working_day_id is not None:
            stmt = stmt.where(TimeSlot.working_day_id == working_day_id)
        if slot_type is not None:
            stmt = stmt.where(TimeSlot.slot_type == slot_type)
        if is_break is not None:
            stmt = stmt.where(TimeSlot.is_break == is_break)
        if is_active is not None:
            stmt = stmt.where(TimeSlot.is_active == is_active)

        # Sorting
        if sort_by == "start_time":
            stmt = stmt.order_by(
                TimeSlot.start_time.asc(), TimeSlot.display_order.asc()
            )
        else:
            stmt = stmt.order_by(
                TimeSlot.display_order.asc(), TimeSlot.start_time.asc()
            )

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_working_day_slots(
        self, school_id: uuid.UUID, working_day_id: uuid.UUID
    ) -> Sequence[TimeSlot]:
        """Fetch all non-deleted time slots configured for a specific working day."""
        stmt = (
            select(TimeSlot)
            .where(
                TimeSlot.school_id == school_id,
                TimeSlot.working_day_id == working_day_id,
                TimeSlot.is_deleted == False,
            )
            .order_by(TimeSlot.display_order.asc(), TimeSlot.start_time.asc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def save_time_slot(self, time_slot: TimeSlot) -> TimeSlot:
        self.session.add(time_slot)
        await self.session.flush()
        return time_slot

    # --- Periods ---
    async def get_period(self, id: uuid.UUID, school_id: uuid.UUID) -> Period | None:
        stmt = select(Period).where(
            Period.id == id,
            Period.school_id == school_id,
            Period.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_periods(
        self,
        school_id: uuid.UUID,
        time_slot_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Period]:
        stmt = select(Period).where(
            Period.school_id == school_id,
            Period.is_deleted == False,
        )

        if time_slot_id is not None:
            stmt = stmt.where(Period.time_slot_id == time_slot_id)
        if class_id is not None:
            stmt = stmt.where(Period.class_id == class_id)
        if is_active is not None:
            stmt = stmt.where(Period.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_period(self, period: Period) -> Period:
        self.session.add(period)
        await self.session.flush()
        return period

    # --- Break Periods ---
    async def get_break_period(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> BreakPeriod | None:
        stmt = select(BreakPeriod).where(
            BreakPeriod.id == id,
            BreakPeriod.school_id == school_id,
            BreakPeriod.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_break_periods(
        self,
        school_id: uuid.UUID,
        time_slot_id: uuid.UUID | None = None,
        break_type: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[BreakPeriod]:
        stmt = select(BreakPeriod).where(
            BreakPeriod.school_id == school_id,
            BreakPeriod.is_deleted == False,
        )

        if time_slot_id is not None:
            stmt = stmt.where(BreakPeriod.time_slot_id == time_slot_id)
        if break_type is not None:
            stmt = stmt.where(BreakPeriod.break_type == break_type)
        if is_active is not None:
            stmt = stmt.where(BreakPeriod.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_break_period(self, break_period: BreakPeriod) -> BreakPeriod:
        self.session.add(break_period)
        await self.session.flush()
        return break_period
