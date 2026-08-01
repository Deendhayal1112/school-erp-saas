import datetime
import uuid

from pydantic import BaseModel, Field

from app.modules.academic_calendar.enums import (
    CalendarEventType,
    DayOfWeek,
    HolidayType,
)

# ===========================================================================
# WORKING DAY SCHEMAS
# ===========================================================================


class WorkingDayBase(BaseModel):
    day_of_week: DayOfWeek
    is_working: bool = True
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    default_break_minutes: int = Field(45, ge=0, le=240)
    display_order: int = Field(0, ge=0)


class WorkingDayCreate(WorkingDayBase):
    academic_year_id: uuid.UUID


class WorkingDayUpdate(BaseModel):
    is_working: bool | None = None
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    default_break_minutes: int | None = Field(None, ge=0, le=240)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class WorkingDayResponse(WorkingDayBase):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# ===========================================================================
# HOLIDAY SCHEMAS
# ===========================================================================


class HolidayBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    holiday_type: HolidayType
    start_date: datetime.date
    end_date: datetime.date
    description: str | None = None
    is_recurring: bool = False


class HolidayCreate(HolidayBase):
    academic_year_id: uuid.UUID


class HolidayUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    holiday_type: HolidayType | None = None
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    description: str | None = None
    is_recurring: bool | None = None
    is_active: bool | None = None


class HolidayResponse(HolidayBase):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# ===========================================================================
# SPECIAL WORKING DAY SCHEMAS
# ===========================================================================


class SpecialWorkingDayBase(BaseModel):
    date: datetime.date
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    description: str | None = None


class SpecialWorkingDayCreate(SpecialWorkingDayBase):
    academic_year_id: uuid.UUID


class SpecialWorkingDayUpdate(BaseModel):
    date: datetime.date | None = None
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    description: str | None = None
    is_active: bool | None = None


class SpecialWorkingDayResponse(SpecialWorkingDayBase):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


# ===========================================================================
# ACADEMIC CALENDAR SCHEMAS
# ===========================================================================


class AcademicCalendarBase(BaseModel):
    term_id: uuid.UUID | None = None
    date: datetime.date
    event_name: str = Field(..., min_length=2, max_length=150)
    event_type: CalendarEventType
    description: str | None = None
    holiday_flag: bool = False
    working_day_flag: bool = True


class AcademicCalendarCreate(AcademicCalendarBase):
    academic_year_id: uuid.UUID


class AcademicCalendarUpdate(BaseModel):
    term_id: uuid.UUID | None = None
    date: datetime.date | None = None
    event_name: str | None = Field(None, min_length=2, max_length=150)
    event_type: CalendarEventType | None = None
    description: str | None = None
    holiday_flag: bool | None = None
    working_day_flag: bool | None = None
    is_active: bool | None = None


class AcademicCalendarResponse(AcademicCalendarBase):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class GenerateCalendarRequest(BaseModel):
    academic_year_id: uuid.UUID


class CalendarSummaryResponse(BaseModel):
    total_days: int
    working_days: int
    holidays: int
    events: int
