import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.academic_calendar.enums import (
    CalendarEventType,
    DayOfWeek,
)
from app.modules.academic_calendar.exceptions import (
    AcademicCalendarNotFoundException,
    AcademicYearNotFoundException,
    DuplicateCalendarDateException,
    HolidayNotFoundException,
    SpecialWorkingDayNotFoundException,
    TermNotFoundException,
    WorkingDayNotFoundException,
)
from app.modules.academic_calendar.models import (
    AcademicCalendar,
    Holiday,
    SpecialWorkingDay,
    WorkingDay,
)
from app.modules.academic_calendar.repository import AcademicCalendarRepository
from app.modules.academic_calendar.schemas import (
    AcademicCalendarCreate,
    AcademicCalendarUpdate,
    HolidayCreate,
    HolidayUpdate,
    SpecialWorkingDayCreate,
    SpecialWorkingDayUpdate,
    WorkingDayCreate,
    WorkingDayUpdate,
)
from app.modules.academic_calendar.validators import (
    validate_date_range,
    validate_working_hours,
)
from app.modules.academic_year.models import AcademicYear
from app.modules.term.models import Term

logger = logging.getLogger(__name__)


class AcademicCalendarService:
    """
    Service layer orchestrating all operating schedule, holiday configurations,
    special working days, and bulk day-by-day academic calendar generation.
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = AcademicCalendarRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    # ===========================================================================
    # VALIDATION HELPERS
    # ===========================================================================

    async def _verify_academic_year_exists(self, school_id: uuid.UUID, academic_year_id: uuid.UUID) -> None:
        stmt = select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
        )
        ay = (await self.db.execute(stmt)).scalar_one_or_none()
        if not ay:
            raise AcademicYearNotFoundException()

    async def _verify_term_exists(self, school_id: uuid.UUID, term_id: uuid.UUID) -> None:
        stmt = select(Term).where(
            Term.id == term_id,
            Term.school_id == school_id,
            Term.is_deleted == False,
        )
        t = (await self.db.execute(stmt)).scalar_one_or_none()
        if not t:
            raise TermNotFoundException()

    # ===========================================================================
    # CACHE HELPERS
    # ===========================================================================

    async def _clear_caches(self, school_id: uuid.UUID, academic_year_id: uuid.UUID) -> None:
        await self.cache.delete(f"calendar:working_days:{school_id}:{academic_year_id}")
        await self.cache.delete(f"calendar:holidays:{school_id}:{academic_year_id}")
        await self.cache.delete(f"calendar:entries:{school_id}:{academic_year_id}")

    # ===========================================================================
    # WORKING DAYS SERVICE METHODS
    # ===========================================================================

    async def get_working_day(self, id: uuid.UUID, school_id: uuid.UUID) -> WorkingDay:
        wd = await self.repo.get_working_day(id, school_id)
        if not wd:
            raise WorkingDayNotFoundException()
        return wd

    async def get_working_days_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[WorkingDay]:
        wds = await self.repo.get_working_days_by_year(school_id, academic_year_id)
        # If wds don't exist yet, we initialize Monday-Sunday as inactive/active default values
        if not wds:
            await self._verify_academic_year_exists(school_id, academic_year_id)
            defaults = [
                (DayOfWeek.MONDAY, True, 0),
                (DayOfWeek.TUESDAY, True, 1),
                (DayOfWeek.WEDNESDAY, True, 2),
                (DayOfWeek.THURSDAY, True, 3),
                (DayOfWeek.FRIDAY, True, 4),
                (DayOfWeek.SATURDAY, False, 5),
                (DayOfWeek.SUNDAY, False, 6),
            ]
            import datetime
            wds = []
            for dow, working, order in defaults:
                wd = WorkingDay(
                    school_id=school_id,
                    academic_year_id=academic_year_id,
                    day_of_week=dow,
                    is_working=working,
                    start_time=datetime.time(8, 0) if working else None,
                    end_time=datetime.time(16, 0) if working else None,
                    default_break_minutes=45,
                    display_order=order,
                )
                await self.repo.save_working_day(wd)
            await self.db.flush()
            wds = await self.repo.get_working_days_by_year(school_id, academic_year_id)

        # Refresh all to avoid MissingGreenlet on response serialization
        for w in wds:
            await self.db.refresh(w)
        return wds

    async def create_working_day(
        self, school_id: uuid.UUID, data: WorkingDayCreate, actor: User
    ) -> WorkingDay:
        await self._verify_academic_year_exists(school_id, data.academic_year_id)
        validate_working_hours(data.start_time, data.end_time)

        # Check for duplicate
        existing = await self.repo.get_working_days_by_year(school_id, data.academic_year_id)
        if any(w.day_of_week == data.day_of_week for w in existing):
            raise DuplicateCalendarDateException(f"Working day configuration for {data.day_of_week} already exists.")

        wd = WorkingDay(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            day_of_week=data.day_of_week,
            is_working=data.is_working,
            start_time=data.start_time,
            end_time=data.end_time,
            default_break_minutes=data.default_break_minutes,
            display_order=data.display_order,
        )
        await self.repo.save_working_day(wd)
        await self.db.flush()
        await self.db.refresh(wd)
        await self._clear_caches(school_id, data.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="working_day.create",
            entity_name="WorkingDay",
            entity_id=wd.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return wd

    async def update_working_day(
        self, id: uuid.UUID, school_id: uuid.UUID, data: WorkingDayUpdate, actor: User
    ) -> WorkingDay:
        wd = await self.get_working_day(id, school_id)

        if data.is_working is not None:
            wd.is_working = data.is_working
        if data.start_time is not None:
            wd.start_time = data.start_time
        if data.end_time is not None:
            wd.end_time = data.end_time
        if data.default_break_minutes is not None:
            wd.default_break_minutes = data.default_break_minutes
        if data.display_order is not None:
            wd.display_order = data.display_order
        if data.is_active is not None:
            wd.is_active = data.is_active

        validate_working_hours(wd.start_time, wd.end_time)

        await self.repo.save_working_day(wd)
        await self.db.flush()
        await self.db.refresh(wd)
        await self._clear_caches(school_id, wd.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="working_day.update",
            entity_name="WorkingDay",
            entity_id=wd.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return wd

    async def delete_working_day(self, id: uuid.UUID, school_id: uuid.UUID, actor: User) -> None:
        wd = await self.get_working_day(id, school_id)
        wd.is_deleted = True
        wd.deleted_at = datetime.now()
        await self.repo.save_working_day(wd)
        await self.db.flush()
        await self._clear_caches(school_id, wd.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="working_day.delete",
            entity_name="WorkingDay",
            entity_id=wd.id,
            user_id=actor.id,
            school_id=school_id,
        )

# ===========================================================================
# HOLIDAYS SERVICE METHODS
# ===========================================================================

    async def get_holiday(self, id: uuid.UUID, school_id: uuid.UUID) -> Holiday:
        h = await self.repo.get_holiday(id, school_id)
        if not h:
            raise HolidayNotFoundException()
        return h

    async def get_holidays_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[Holiday]:
        res = await self.repo.get_holidays_by_year(school_id, academic_year_id)
        for h in res:
            await self.db.refresh(h)
        return res

    async def create_holiday(
        self, school_id: uuid.UUID, data: HolidayCreate, actor: User
    ) -> Holiday:
        await self._verify_academic_year_exists(school_id, data.academic_year_id)
        validate_date_range(data.start_date, data.end_date)

        h = Holiday(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            holiday_type=data.holiday_type,
            start_date=data.start_date,
            end_date=data.end_date,
            description=data.description,
            is_recurring=data.is_recurring,
        )
        await self.repo.save_holiday(h)
        await self.db.flush()
        await self.db.refresh(h)
        await self._clear_caches(school_id, data.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="holiday.create",
            entity_name="Holiday",
            entity_id=h.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return h

    async def update_holiday(
        self, id: uuid.UUID, school_id: uuid.UUID, data: HolidayUpdate, actor: User
    ) -> Holiday:
        h = await self.get_holiday(id, school_id)

        if data.name is not None:
            h.name = data.name
        if data.holiday_type is not None:
            h.holiday_type = data.holiday_type
        if data.start_date is not None:
            h.start_date = data.start_date
        if data.end_date is not None:
            h.end_date = data.end_date
        if data.description is not None:
            h.description = data.description
        if data.is_recurring is not None:
            h.is_recurring = data.is_recurring
        if data.is_active is not None:
            h.is_active = data.is_active

        validate_date_range(h.start_date, h.end_date)

        await self.repo.save_holiday(h)
        await self.db.flush()
        await self.db.refresh(h)
        await self._clear_caches(school_id, h.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="holiday.update",
            entity_name="Holiday",
            entity_id=h.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return h

    async def delete_holiday(self, id: uuid.UUID, school_id: uuid.UUID, actor: User) -> None:
        h = await self.get_holiday(id, school_id)
        h.is_deleted = True
        h.deleted_at = datetime.now()
        await self.repo.save_holiday(h)
        await self.db.flush()
        await self._clear_caches(school_id, h.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="holiday.delete",
            entity_name="Holiday",
            entity_id=h.id,
            user_id=actor.id,
            school_id=school_id,
        )

# ===========================================================================
# SPECIAL WORKING DAYS SERVICE METHODS
# ===========================================================================

    async def get_special_working_day(self, id: uuid.UUID, school_id: uuid.UUID) -> SpecialWorkingDay:
        swd = await self.repo.get_special_working_day(id, school_id)
        if not swd:
            raise SpecialWorkingDayNotFoundException()
        return swd

    async def get_special_working_days_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[SpecialWorkingDay]:
        res = await self.repo.get_special_working_days_by_year(school_id, academic_year_id)
        for s in res:
            await self.db.refresh(s)
        return res

    async def create_special_working_day(
        self, school_id: uuid.UUID, data: SpecialWorkingDayCreate, actor: User
    ) -> SpecialWorkingDay:
        await self._verify_academic_year_exists(school_id, data.academic_year_id)
        validate_working_hours(data.start_time, data.end_time)

        # Check duplicates
        existing = await self.repo.get_special_working_days_by_year(school_id, data.academic_year_id)
        if any(s.date == data.date for s in existing):
            raise DuplicateCalendarDateException(f"Special working day configuration for date {data.date} already exists.")

        swd = SpecialWorkingDay(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            date=data.date,
            start_time=data.start_time,
            end_time=data.end_time,
            description=data.description,
        )
        await self.repo.save_special_working_day(swd)
        await self.db.flush()
        await self.db.refresh(swd)
        await self._clear_caches(school_id, data.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="special_working_day.create",
            entity_name="SpecialWorkingDay",
            entity_id=swd.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return swd

    async def update_special_working_day(
        self, id: uuid.UUID, school_id: uuid.UUID, data: SpecialWorkingDayUpdate, actor: User
    ) -> SpecialWorkingDay:
        swd = await self.get_special_working_day(id, school_id)

        if data.date is not None:
            swd.date = data.date
        if data.start_time is not None:
            swd.start_time = data.start_time
        if data.end_time is not None:
            swd.end_time = data.end_time
        if data.description is not None:
            swd.description = data.description
        if data.is_active is not None:
            swd.is_active = data.is_active

        validate_working_hours(swd.start_time, swd.end_time)

        await self.repo.save_special_working_day(swd)
        await self.db.flush()
        await self.db.refresh(swd)
        await self._clear_caches(school_id, swd.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="special_working_day.update",
            entity_name="SpecialWorkingDay",
            entity_id=swd.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return swd

    async def delete_special_working_day(self, id: uuid.UUID, school_id: uuid.UUID, actor: User) -> None:
        swd = await self.get_special_working_day(id, school_id)
        swd.is_deleted = True
        swd.deleted_at = datetime.now()
        await self.repo.save_special_working_day(swd)
        await self.db.flush()
        await self._clear_caches(school_id, swd.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="special_working_day.delete",
            entity_name="SpecialWorkingDay",
            entity_id=swd.id,
            user_id=actor.id,
            school_id=school_id,
        )

# ===========================================================================
# ACADEMIC CALENDAR SERVICE METHODS
# ===========================================================================

    async def get_calendar_entry(self, id: uuid.UUID, school_id: uuid.UUID) -> AcademicCalendar:
        c = await self.repo.get_calendar_entry(id, school_id)
        if not c:
            raise AcademicCalendarNotFoundException()
        return c

    async def get_calendar_entries_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> list[AcademicCalendar]:
        res = await self.repo.get_calendar_entries_by_year(school_id, academic_year_id)
        for c in res:
            await self.db.refresh(c)
        return res

    async def get_calendar_entries_by_month(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID, year: int, month: int
    ) -> list[AcademicCalendar]:
        res = await self.repo.get_calendar_entries_by_month(school_id, academic_year_id, year, month)
        for c in res:
            await self.db.refresh(c)
        return res

    async def create_calendar_entry(
        self, school_id: uuid.UUID, data: AcademicCalendarCreate, actor: User
    ) -> AcademicCalendar:
        await self._verify_academic_year_exists(school_id, data.academic_year_id)
        if data.term_id is not None:
            await self._verify_term_exists(school_id, data.term_id)

        c = AcademicCalendar(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            date=data.date,
            event_name=data.event_name,
            event_type=data.event_type,
            description=data.description,
            holiday_flag=data.holiday_flag,
            working_day_flag=data.working_day_flag,
        )
        await self.repo.save_calendar_entry(c)
        await self.db.flush()
        await self.db.refresh(c)
        await self._clear_caches(school_id, data.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="calendar_event.create",
            entity_name="AcademicCalendar",
            entity_id=c.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return c

    async def update_calendar_entry(
        self, id: uuid.UUID, school_id: uuid.UUID, data: AcademicCalendarUpdate, actor: User
    ) -> AcademicCalendar:
        c = await self.get_calendar_entry(id, school_id)

        if data.term_id is not None:
            await self._verify_term_exists(school_id, data.term_id)
            c.term_id = data.term_id
        if data.date is not None:
            c.date = data.date
        if data.event_name is not None:
            c.event_name = data.event_name
        if data.event_type is not None:
            c.event_type = data.event_type
        if data.description is not None:
            c.description = data.description
        if data.holiday_flag is not None:
            c.holiday_flag = data.holiday_flag
        if data.working_day_flag is not None:
            c.working_day_flag = data.working_day_flag
        if data.is_active is not None:
            c.is_active = data.is_active

        await self.repo.save_calendar_entry(c)
        await self.db.flush()
        await self.db.refresh(c)
        await self._clear_caches(school_id, c.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="calendar_event.update",
            entity_name="AcademicCalendar",
            entity_id=c.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return c

    async def delete_calendar_entry(self, id: uuid.UUID, school_id: uuid.UUID, actor: User) -> None:
        c = await self.get_calendar_entry(id, school_id)
        c.is_deleted = True
        c.deleted_at = datetime.now()
        await self.repo.save_calendar_entry(c)
        await self.db.flush()
        await self._clear_caches(school_id, c.academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="calendar_event.delete",
            entity_name="AcademicCalendar",
            entity_id=c.id,
            user_id=actor.id,
            school_id=school_id,
        )

    async def calculate_working_days(
        self, school_id: uuid.UUID, start_date: date, end_date: date
    ) -> int:
        validate_date_range(start_date, end_date)
        entries = await self.repo.get_calendar_entries_in_range(school_id, start_date, end_date)
        return sum(1 for e in entries if e.working_day_flag and not e.is_deleted)

    async def generate_calendar(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID, actor: User
    ) -> int:
        # 1. Fetch Academic Year dates
        stmt = select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
        )
        ay = (await self.db.execute(stmt)).scalar_one_or_none()
        if not ay:
            raise AcademicYearNotFoundException()

        # 2. Fetch associated terms
        stmt_terms = select(Term).where(
            Term.academic_year_id == academic_year_id,
            Term.school_id == school_id,
            Term.is_deleted == False,
        )
        terms = list((await self.db.execute(stmt_terms)).scalars().all())

        # 3. Clean existing generated entries
        await self.repo.delete_calendar_entries_by_year(school_id, academic_year_id)

        # 4. Fetch Working Days configs
        wds = await self.get_working_day_configs_dict(school_id, academic_year_id)

        # 5. Fetch Holidays overlapping this academic year range
        holidays = await self.repo.get_holidays_in_range(school_id, ay.start_date, ay.end_date)

        # 6. Fetch Special Working Days
        special_days = await self.repo.get_special_working_days_in_range(school_id, ay.start_date, ay.end_date)
        special_days_dict = {sd.date: sd for sd in special_days}

        # 7. Generate entries day by day
        current_date = ay.start_date
        new_entries = []

        # Weekdays matching enums
        weekday_map = {
            0: DayOfWeek.MONDAY,
            1: DayOfWeek.TUESDAY,
            2: DayOfWeek.WEDNESDAY,
            3: DayOfWeek.THURSDAY,
            4: DayOfWeek.FRIDAY,
            5: DayOfWeek.SATURDAY,
            6: DayOfWeek.SUNDAY,
        }

        while current_date <= ay.end_date:
            # Resolve corresponding Term
            matching_term = None
            for t in terms:
                if t.start_date <= current_date <= t.end_date:
                    matching_term = t
                    break

            # Check if there is a Holiday matching this date
            matching_holiday = None
            for h in holidays:
                if h.start_date <= current_date <= h.end_date:
                    matching_holiday = h
                    break

            # Check Special Working Day override
            special_wd = special_days_dict.get(current_date)

            # Check Default Weekday operating status
            day_enum = weekday_map[current_date.weekday()]
            wd_config = wds.get(day_enum)
            default_is_working = wd_config.is_working if wd_config else True

            # Resolve Flags and naming
            if matching_holiday:
                holiday_flag = True
                working_day_flag = False
                event_name = matching_holiday.name
                event_type = CalendarEventType.HOLIDAY
                desc = matching_holiday.description
            elif special_wd:
                holiday_flag = False
                working_day_flag = True
                event_name = special_wd.description or "Special Working Day"
                event_type = CalendarEventType.ACADEMIC
                desc = "Special makeup operating day overrides weekend default"
            else:
                holiday_flag = not default_is_working
                working_day_flag = default_is_working
                event_name = "Regular Class" if default_is_working else "Weekend"
                event_type = CalendarEventType.ACADEMIC if default_is_working else CalendarEventType.HOLIDAY
                desc = None

            entry = AcademicCalendar(
                school_id=school_id,
                academic_year_id=academic_year_id,
                term_id=matching_term.id if matching_term else None,
                date=current_date,
                event_name=event_name,
                event_type=event_type,
                description=desc,
                holiday_flag=holiday_flag,
                working_day_flag=working_day_flag,
            )
            new_entries.append(entry)
            current_date += timedelta(days=1)

        # Bulk save
        if new_entries:
            await self.repo.save_calendar_entries_bulk(new_entries)
            await self.db.flush()

        await self._clear_caches(school_id, academic_year_id)

        await self.audit.log_action(
            module="academic_calendar",
            action="calendar.generate",
            entity_name="AcademicCalendar",
            entity_id=academic_year_id,
            user_id=actor.id,
            school_id=school_id,
        )

        return len(new_entries)

    async def get_working_day_configs_dict(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> dict[DayOfWeek, WorkingDay]:
        wds = await self.get_working_days_by_year(school_id, academic_year_id)
        return {wd.day_of_week: wd for wd in wds}
