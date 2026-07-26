import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.subject_group.enums import SubjectGroupStatus
from app.modules.subject_management.schemas import SubjectResponse


class SubjectGroupBase(BaseModel):
    group_code: str = Field(
        ..., min_length=1, max_length=50, description="Unique group code"
    )
    group_name: str = Field(
        ..., min_length=1, max_length=100, description="Unique group name"
    )
    display_name: str = Field(
        ..., min_length=1, max_length=100, description="Display Label"
    )
    description: str | None = Field(None, description="Detailed description")
    category: str = Field(
        ..., min_length=1, max_length=50, description="Science, Arts, Commerce, etc."
    )

    display_order: int = Field(default=0, ge=0)
    minimum_subjects: int = Field(default=0, ge=0)
    maximum_subjects: int = Field(default=0, ge=0)

    is_core: bool = Field(default=True)
    is_elective: bool = Field(default=False)


class SubjectGroupCreate(SubjectGroupBase):
    @model_validator(mode="after")
    def validate_create_fields(self) -> "SubjectGroupCreate":
        if self.maximum_subjects < self.minimum_subjects:
            raise ValueError(
                "Maximum Subjects must be greater than or equal to Minimum Subjects."
            )

        if self.is_core and self.is_elective:
            raise ValueError(
                "A subject group cannot be both a Core and an Elective group."
            )

        return self


class SubjectGroupUpdate(BaseModel):
    group_code: str | None = Field(None, min_length=1, max_length=50)
    group_name: str | None = Field(None, min_length=1, max_length=100)
    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    category: str | None = Field(None, min_length=1, max_length=50)

    display_order: int | None = Field(None, ge=0)
    minimum_subjects: int | None = Field(None, ge=0)
    maximum_subjects: int | None = Field(None, ge=0)

    is_core: bool | None = None
    is_elective: bool | None = None


class SubjectGroupResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    group_code: str
    group_name: str
    display_name: str
    description: str | None
    category: str

    display_order: int
    minimum_subjects: int
    maximum_subjects: int

    is_core: bool
    is_elective: bool
    is_locked: bool
    status: SubjectGroupStatus

    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectMappingCreate(BaseModel):
    subject_id: uuid.UUID = Field(..., description="Target Subject UUID to map")
    display_order: int = Field(default=0, ge=0)
    is_mandatory: bool = Field(default=True)


class SubjectMappingResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    subject_group_id: uuid.UUID
    subject_id: uuid.UUID
    display_order: int
    is_mandatory: bool
    created_at: datetime
    updated_at: datetime
    subject: SubjectResponse | None = None

    model_config = ConfigDict(from_attributes=True)
