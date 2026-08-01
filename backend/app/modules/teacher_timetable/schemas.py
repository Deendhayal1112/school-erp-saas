import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.class_timetable.enums import LessonType
from app.modules.teacher_timetable.enums import (
    TeacherAvailabilityStatus,
    TeacherTimetableStatus,
)


# --- Teacher Timetable ---
class TeacherTimetableBase(BaseModel):
    teacher_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    academic_year_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    term_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    name: str = Field(..., max_length=100, examples=["Mr. Smith Term 1 Schedule"])
    effective_from: datetime.date = Field(..., examples=["2026-06-01"])
    effective_to: datetime.date | None = Field(None, examples=["2026-10-31"])
    remarks: str | None = Field(None, examples=["Initial sync from class timetables"])
    status: TeacherTimetableStatus = Field(
        default=TeacherTimetableStatus.DRAFT, examples=["DRAFT"]
    )


class TeacherTimetableCreate(TeacherTimetableBase):
    pass


class TeacherTimetableUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    effective_from: datetime.date | None = None
    effective_to: datetime.date | None = None
    remarks: str | None = None
    status: TeacherTimetableStatus | None = None
    is_active: bool | None = None


class TeacherTimetableResponse(TeacherTimetableBase):
    id: uuid.UUID
    school_id: uuid.UUID
    version: int
    is_locked: bool
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Teacher Timetable Entry ---
class TeacherTimetableEntryBase(BaseModel):
    working_day_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    time_slot_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    class_timetable_entry_id: uuid.UUID | None = Field(
        None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    class_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    section_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    subject_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    room_id: uuid.UUID | None = Field(
        None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    lesson_type: LessonType = Field(default=LessonType.THEORY, examples=["THEORY"])
    remarks: str | None = Field(None, examples=["Physics lab session"])


class TeacherTimetableEntryCreate(TeacherTimetableEntryBase):
    teacher_timetable_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )


class TeacherTimetableEntryUpdate(BaseModel):
    working_day_id: uuid.UUID | None = None
    time_slot_id: uuid.UUID | None = None
    class_timetable_entry_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    lesson_type: LessonType | None = None
    remarks: str | None = None


class TeacherTimetableEntryResponse(TeacherTimetableEntryBase):
    id: uuid.UUID
    school_id: uuid.UUID
    teacher_timetable_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Teacher Availability ---
class TeacherAvailabilityBase(BaseModel):
    teacher_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    working_day_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    time_slot_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    availability_status: TeacherAvailabilityStatus = Field(
        default=TeacherAvailabilityStatus.AVAILABLE, examples=["AVAILABLE"]
    )
    reason: str | None = Field(None, max_length=255, examples=["Medical appointment"])


class TeacherAvailabilityCreate(TeacherAvailabilityBase):
    pass


class TeacherAvailabilityUpdate(BaseModel):
    availability_status: TeacherAvailabilityStatus | None = None
    reason: str | None = Field(None, max_length=255)


class TeacherAvailabilityResponse(TeacherAvailabilityBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Weekly Schedule Cell/Response ---
class TeacherTimetableEntrySummary(BaseModel):
    entry_id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    section_id: uuid.UUID
    section_name: str
    subject_id: uuid.UUID
    subject_name: str
    room_id: uuid.UUID | None = None
    room_name: str | None = None
    lesson_type: LessonType
    remarks: str | None = None


class TeacherAvailabilitySummary(BaseModel):
    availability_id: uuid.UUID
    availability_status: TeacherAvailabilityStatus
    reason: str | None = None


class TeacherDayScheduleSummary(BaseModel):
    working_day_id: uuid.UUID
    day_of_week: str
    is_working: bool
    entries: list[TeacherTimetableEntrySummary]
    availabilities: list[TeacherAvailabilitySummary]


class TeacherWeeklyScheduleResponse(BaseModel):
    teacher_timetable_id: uuid.UUID
    teacher_id: uuid.UUID
    teacher_name: str
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    name: str
    status: TeacherTimetableStatus
    version: int
    schedule: list[TeacherDayScheduleSummary]

    model_config = ConfigDict(from_attributes=True)
