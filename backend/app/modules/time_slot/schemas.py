import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.time_slot.enums import BreakType, SlotType


# --- Time Slot Schemas ---
class TimeSlotBase(BaseModel):
    name: str = Field(..., max_length=100, examples=["Period 1", "Lunch Break"])
    slot_number: int = Field(..., ge=1, examples=[1])
    start_time: datetime.time = Field(..., examples=["08:30:00"])
    end_time: datetime.time = Field(..., examples=["09:15:00"])
    duration_minutes: int = Field(..., ge=1, examples=[45])
    slot_type: SlotType = Field(default=SlotType.TEACHING, examples=["TEACHING"])
    working_day_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    display_order: int = Field(default=0, ge=0, examples=[0])
    is_break: bool = Field(default=False, examples=[False])
    is_teaching: bool = Field(default=True, examples=[True])
    is_active: bool = Field(default=True, examples=[True])


class TimeSlotCreate(TimeSlotBase):
    academic_year_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )


class TimeSlotUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    slot_number: int | None = Field(None, ge=1)
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    duration_minutes: int | None = Field(None, ge=1)
    slot_type: SlotType | None = None
    display_order: int | None = Field(None, ge=0)
    is_break: bool | None = None
    is_teaching: bool | None = None
    is_active: bool | None = None


class TimeSlotResponse(TimeSlotBase):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_locked: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Period Schemas ---
class PeriodBase(BaseModel):
    time_slot_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    class_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    default_subject_duration_minutes: int = Field(default=45, ge=1, examples=[45])
    default_teacher_duration_minutes: int = Field(default=45, ge=1, examples=[45])
    max_capacity: int | None = Field(None, ge=1, examples=[40])


class PeriodCreate(PeriodBase):
    pass


class PeriodUpdate(BaseModel):
    default_subject_duration_minutes: int | None = Field(None, ge=1)
    default_teacher_duration_minutes: int | None = Field(None, ge=1)
    max_capacity: int | None = Field(None, ge=1)
    is_active: bool | None = None


class PeriodResponse(PeriodBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Break Period Schemas ---
class BreakPeriodBase(BaseModel):
    time_slot_id: uuid.UUID = Field(
        ..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
    )
    break_type: BreakType = Field(
        default=BreakType.SHORT_BREAK, examples=["SHORT_BREAK"]
    )
    name: str = Field(..., max_length=100, examples=["Recess", "Lunch"])
    duration_minutes: int = Field(..., ge=1, examples=[15])
    description: str | None = Field(None, examples=["Morning tea break"])


class BreakPeriodCreate(BreakPeriodBase):
    pass


class BreakPeriodUpdate(BaseModel):
    break_type: BreakType | None = None
    name: str | None = Field(None, max_length=100)
    duration_minutes: int | None = Field(None, ge=1)
    description: str | None = None
    is_active: bool | None = None


class BreakPeriodResponse(BreakPeriodBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)
