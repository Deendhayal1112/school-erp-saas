import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.section_management.enums import SectionStatus


class SectionBase(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=50, description="Section Name (e.g. Section A)"
    )
    code: str = Field(
        ..., min_length=1, max_length=50, description="Section Code (e.g. SEC-A-G1)"
    )
    display_name: str = Field(
        ..., min_length=1, max_length=50, description="Section display label"
    )
    description: str | None = Field(None, description="Optional description details")
    capacity: int = Field(
        ..., ge=1, description="Student enrollment capacity for this section"
    )
    display_order: int = Field(
        ..., ge=0, description="Sorting priority within the class"
    )
    room_number: str | None = Field(None, max_length=50)
    floor: str | None = Field(None, max_length=50)
    building: str | None = Field(None, max_length=50)


class SectionCreate(SectionBase):
    academic_year_id: uuid.UUID = Field(..., description="Target Academic Year UUID")
    class_id: uuid.UUID = Field(..., description="Target Class UUID")


class SectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    code: str | None = Field(None, min_length=1, max_length=50)
    display_name: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = None
    capacity: int | None = Field(None, ge=1)
    display_order: int | None = Field(None, ge=0)
    room_number: str | None = Field(None, max_length=50)
    floor: str | None = Field(None, max_length=50)
    building: str | None = Field(None, max_length=50)


class SectionResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    class_id: uuid.UUID
    name: str
    code: str
    display_name: str
    description: str | None
    capacity: int
    display_order: int
    room_number: str | None
    floor: str | None
    building: str | None
    is_active: bool
    is_default: bool
    is_locked: bool
    status: SectionStatus
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
