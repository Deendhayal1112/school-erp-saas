import uuid
from datetime import date

from sqlalchemy import delete, extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic_calendar.models import (
    AcademicCalendar,
    Holiday,
    SpecialWorkingDay,
    WorkingDay,
)


class AcademicCalendarRepository:
    """
    Repository class executing optimized Async SQLAlchemy queries for Working Days,
    Holidays, Special Working Days, and Academic Calendar entries with tenant isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===========================================================================
    # WORKING DAYS
    # ===========================================================================

    async def get_working_day(self, id: uuid.UUID, school_id: uuid.UUID) -> WorkingDay | None:
        stmt = select(WorkingDay).where(
            WorkingDay.id == id,
            WorkingDay.school_id == school_id,
            WorkingDay.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_working_days_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[WorkingDay]:
        stmt = (
            select(WorkingDay)
            .where(
                WorkingDay.school_id == school_id,
                WorkingDay.academic_year_id == academic_year_id,
                WorkingDay.is_deleted == False,
            )
            .order_by(WorkingDay.display_order.asc(), WorkingDay.day_of_week.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def save_working_day(self, working_day: WorkingDay) -> WorkingDay:
        self.session.add(working_day)
        await self.session.flush()
        return working_day

    # ===========================================================================
    # HOLIDAYS
    # ===========================================================================

    async def get_holiday(self, id: uuid.UUID, school_id: uuid.UUID) -> Holiday | None:
        stmt = select(Holiday).where(
            Holiday.id == id,
            Holiday.school_id == school_id,
            Holiday.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_holidays_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[Holiday]:
        stmt = (
            select(Holiday)
            .where(
                Holiday.school_id == school_id,
                Holiday.academic_year_id == academic_year_id,
                Holiday.is_deleted == False,
            )
            .order_by(Holiday.start_date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_holidays_in_range(
        self, school_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[Holiday]:
        # Overlapping ranges: start_date <= Holiday.end_date AND end_date >= Holiday.start_date
        stmt = (
            select(Holiday)
            .where(
                Holiday.school_id == school_id,
                Holiday.is_deleted == False,
                Holiday.start_date <= end_date,
                Holiday.end_date >= start_date,
            )
            .order_by(Holiday.start_date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def save_holiday(self, holiday: Holiday) -> Holiday:
        self.session.add(holiday)
        await self.session.flush()
        return holiday

    # ===========================================================================
    # SPECIAL WORKING DAYS
    # ===========================================================================

    async def get_special_working_day(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> SpecialWorkingDay | None:
        stmt = select(SpecialWorkingDay).where(
            SpecialWorkingDay.id == id,
            SpecialWorkingDay.school_id == school_id,
            SpecialWorkingDay.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_special_working_days_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[SpecialWorkingDay]:
        stmt = (
            select(SpecialWorkingDay)
            .where(
                SpecialWorkingDay.school_id == school_id,
                SpecialWorkingDay.academic_year_id == academic_year_id,
                SpecialWorkingDay.is_deleted == False,
            )
            .order_by(SpecialWorkingDay.date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_special_working_days_in_range(
        self, school_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[SpecialWorkingDay]:
        stmt = (
            select(SpecialWorkingDay)
            .where(
                SpecialWorkingDay.school_id == school_id,
                SpecialWorkingDay.is_deleted == False,
                SpecialWorkingDay.date >= start_date,
                SpecialWorkingDay.date <= end_date,
            )
            .order_by(SpecialWorkingDay.date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def save_special_working_day(
        self, special_day: SpecialWorkingDay
    ) -> SpecialWorkingDay:
        self.session.add(special_day)
        await self.session.flush()
        return special_day

    # ===========================================================================
    # ACADEMIC CALENDAR
    # ===========================================================================

    async def get_calendar_entry(
        self, id: uuid.UUID, school_id: uuid.UUID
    ) -> AcademicCalendar | None:
        stmt = select(AcademicCalendar).where(
            AcademicCalendar.id == id,
            AcademicCalendar.school_id == school_id,
            AcademicCalendar.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_calendar_entries_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[AcademicCalendar]:
        stmt = (
            select(AcademicCalendar)
            .where(
                AcademicCalendar.school_id == school_id,
                AcademicCalendar.academic_year_id == academic_year_id,
                AcademicCalendar.is_deleted == False,
            )
            .order_by(AcademicCalendar.date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_calendar_entries_by_month(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID, year: int, month: int
    ) -> list[AcademicCalendar]:
        stmt = (
            select(AcademicCalendar)
            .where(
                AcademicCalendar.school_id == school_id,
                AcademicCalendar.academic_year_id == academic_year_id,
                AcademicCalendar.is_deleted == False,
                extract("year", AcademicCalendar.date) == year,
                extract("month", AcademicCalendar.date) == month,
            )
            .order_by(AcademicCalendar.date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_calendar_entries_in_range(
        self, school_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[AcademicCalendar]:
        stmt = (
            select(AcademicCalendar)
            .where(
                AcademicCalendar.school_id == school_id,
                AcademicCalendar.is_deleted == False,
                AcademicCalendar.date >= start_date,
                AcademicCalendar.date <= end_date,
            )
            .order_by(AcademicCalendar.date.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def save_calendar_entry(self, entry: AcademicCalendar) -> AcademicCalendar:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def save_calendar_entries_bulk(
        self, entries: list[AcademicCalendar]
    ) -> list[AcademicCalendar]:
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def delete_calendar_entries_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> None:
        stmt = delete(AcademicCalendar).where(
            AcademicCalendar.school_id == school_id,
            AcademicCalendar.academic_year_id == academic_year_id,
        )
        await self.session.execute(stmt)
