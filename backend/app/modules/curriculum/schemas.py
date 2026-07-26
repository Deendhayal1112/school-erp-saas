import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.curriculum.enums import CurriculumStatus


class CurriculumUnitBase(BaseModel):
    unit_number: int = Field(..., ge=1, description="Sequential unit number")
    unit_name: str = Field(
        ..., min_length=1, max_length=100, description="Unit topic title"
    )
    description: str | None = None
    learning_outcomes: str | None = None
    estimated_hours: int = Field(default=0, ge=0)
    display_order: int = Field(default=0, ge=0)
    status: str = Field(default="ACTIVE")


class CurriculumUnitCreate(CurriculumUnitBase):
    pass


class CurriculumUnitUpdate(BaseModel):
    unit_number: int | None = Field(None, ge=1)
    unit_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    learning_outcomes: str | None = None
    estimated_hours: int | None = Field(None, ge=0)
    display_order: int | None = Field(None, ge=0)
    status: str | None = None


class CurriculumUnitResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    curriculum_id: uuid.UUID
    unit_number: int
    unit_name: str
    description: str | None
    learning_outcomes: str | None
    estimated_hours: int
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CurriculumBase(BaseModel):
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    class_subject_mapping_id: uuid.UUID

    curriculum_code: str = Field(..., min_length=1, max_length=50)
    curriculum_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None

    learning_objectives: str | None = None
    teaching_methodology: str | None = None
    assessment_strategy: str | None = None
    reference_books: str | None = None

    completion_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    estimated_hours: int = Field(default=0, ge=0)
    display_order: int = Field(default=0, ge=0)
    version: str = Field(default="1.0", max_length=20)

    effective_from: date | None = None
    effective_to: date | None = None


class CurriculumCreate(CurriculumBase):
    @model_validator(mode="after")
    def validate_date_range(self) -> "CurriculumCreate":
        if self.effective_from and self.effective_to:
            if self.effective_from > self.effective_to:
                raise ValueError(
                    "Effective From date cannot be after Effective To date."
                )
        return self


class CurriculumUpdate(BaseModel):
    curriculum_code: str | None = Field(None, min_length=1, max_length=50)
    curriculum_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None

    learning_objectives: str | None = None
    teaching_methodology: str | None = None
    assessment_strategy: str | None = None
    reference_books: str | None = None

    completion_percentage: float | None = Field(None, ge=0.0, le=100.0)
    estimated_hours: int | None = Field(None, ge=0)
    display_order: int | None = Field(None, ge=0)
    version: str | None = Field(None, max_length=20)

    effective_from: date | None = None
    effective_to: date | None = None


class CurriculumResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    class_subject_mapping_id: uuid.UUID

    curriculum_code: str
    curriculum_name: str
    description: str | None

    learning_objectives: str | None
    teaching_methodology: str | None
    assessment_strategy: str | None
    reference_books: str | None

    completion_percentage: float
    estimated_hours: int
    display_order: int

    status: CurriculumStatus
    is_active: bool
    is_locked: bool
    version: str

    effective_from: date | None
    effective_to: date | None

    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
