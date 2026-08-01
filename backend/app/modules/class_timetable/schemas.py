import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.academic_calendar.enums import DayOfWeek
from app.modules.class_timetable.enums import LessonType, TimetableStatus


# --- Class Timetable ---
class ClassTimetableBase(BaseModel):
    academic_year_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    term_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    class_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    section_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    name: str = Field(..., max_length=100, examples=["Grade 10-A Weekly Timetable"])
    effective_from: datetime.date = Field(..., examples=["2026-06-01"])
    effective_to: datetime.date | None = Field(None, examples=["2027-05-31"])
    remarks: str | None = Field(None, examples=["Initial release for Term 1"])
    status: TimetableStatus = Field(default=TimetableStatus.DRAFT, examples=["DRAFT"])


class ClassTimetableCreate(ClassTimetableBase):
    pass


class ClassTimetableUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    effective_from: datetime.date | None = None
    effective_to: datetime.date | None = None
    remarks: str | None = None
    status: TimetableStatus | None = None
    is_active: bool | None = None


class ClassTimetableResponse(ClassTimetableBase):
    id: uuid.UUID
    school_id: uuid.UUID
    version: int
    is_locked: bool
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Class Timetable Entry ---
class ClassTimetableEntryBase(BaseModel):
    working_day_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    time_slot_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    teacher_subject_allocation_id: uuid.UUID | None = Field(
        None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    teacher_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    subject_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    room_id: uuid.UUID | None = Field(
        None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    period_number: int = Field(..., ge=1, examples=[1])
    lesson_type: LessonType = Field(default=LessonType.THEORY, examples=["THEORY"])
    remarks: str | None = Field(None, examples=["Lab practice session"])


class ClassTimetableEntryCreate(ClassTimetableEntryBase):
    timetable_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )


class ClassTimetableEntryUpdate(BaseModel):
    working_day_id: uuid.UUID | None = None
    time_slot_id: uuid.UUID | None = None
    teacher_subject_allocation_id: uuid.UUID | None = None
    teacher_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    period_number: int | None = Field(None, ge=1)
    lesson_type: LessonType | None = None
    remarks: str | None = None


class ClassTimetableEntryResponse(ClassTimetableEntryBase):
    id: uuid.UUID
    school_id: uuid.UUID
    timetable_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Recurring Schedule ---
class RecurringScheduleBase(BaseModel):
    day_of_week: DayOfWeek = Field(..., examples=["MONDAY"])
    recurrence_pattern: str = Field(
        default="WEEKLY", max_length=50, examples=["WEEKLY"]
    )


class RecurringScheduleCreate(RecurringScheduleBase):
    timetable_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )


class RecurringScheduleResponse(RecurringScheduleBase):
    id: uuid.UUID
    school_id: uuid.UUID
    timetable_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Clone Timetable Request ---
class TimetableCloneRequest(BaseModel):
    target_class_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    target_section_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    target_term_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    new_name: str | None = Field(
        None, max_length=100, examples=["Grade 10-B Weekly Timetable"]
    )


# --- Weekly Schedule Cell/Response ---
class TimetableEntrySummary(BaseModel):
    entry_id: uuid.UUID
    period_number: int
    lesson_type: LessonType
    subject_id: uuid.UUID
    subject_name: str
    teacher_id: uuid.UUID
    teacher_name: str
    room_id: uuid.UUID | None = None
    room_name: str | None = None
    remarks: str | None = None


class DayScheduleSummary(BaseModel):
    working_day_id: uuid.UUID
    day_of_week: str
    is_working: bool
    entries: list[TimetableEntrySummary]


class WeeklyScheduleResponse(BaseModel):
    timetable_id: uuid.UUID
    class_id: uuid.UUID
    section_id: uuid.UUID
    term_id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    status: TimetableStatus
    version: int
    schedule: list[DayScheduleSummary]

    model_config = ConfigDict(from_attributes=True)
