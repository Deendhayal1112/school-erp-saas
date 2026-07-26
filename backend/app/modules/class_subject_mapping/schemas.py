import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.class_subject_mapping.enums import ClassSubjectStatus
from app.modules.subject_management.schemas import SubjectResponse


class ClassSubjectBase(BaseModel):
    academic_year_id: uuid.UUID = Field(..., description="Academic Year Reference")
    term_id: uuid.UUID = Field(..., description="Term Reference")
    class_id: uuid.UUID = Field(..., description="Class Reference")
    section_id: uuid.UUID | None = Field(None, description="Optional Section Reference")
    subject_group_id: uuid.UUID | None = Field(
        None, description="Optional Subject Group Reference"
    )
    subject_id: uuid.UUID = Field(..., description="Subject Reference")

    display_order: int = Field(default=0, ge=0)
    weekly_periods: int = Field(..., ge=1)
    theory_periods: int = Field(default=0, ge=0)
    practical_periods: int = Field(default=0, ge=0)
    credits: float = Field(default=0.0, ge=0.0)

    is_compulsory: bool = Field(default=True)
    is_elective: bool = Field(default=False)
    include_in_result: bool = Field(default=True)
    include_in_attendance: bool = Field(default=True)


class ClassSubjectCreate(ClassSubjectBase):
    @model_validator(mode="after")
    def validate_periods(self) -> "ClassSubjectCreate":
        if self.theory_periods + self.practical_periods > self.weekly_periods:
            raise ValueError(
                "Sum of Theory and Practical periods cannot exceed Weekly periods."
            )
        return self


class ClassSubjectUpdate(BaseModel):
    display_order: int | None = Field(None, ge=0)
    weekly_periods: int | None = Field(None, ge=1)
    theory_periods: int | None = Field(None, ge=0)
    practical_periods: int | None = Field(None, ge=0)
    credits: float | None = Field(None, ge=0.0)

    is_compulsory: bool | None = None
    is_elective: bool | None = None
    include_in_result: bool | None = None
    include_in_attendance: bool | None = None


class ClassSubjectResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    class_id: uuid.UUID
    section_id: uuid.UUID | None
    subject_group_id: uuid.UUID | None
    subject_id: uuid.UUID

    display_order: int
    weekly_periods: int
    theory_periods: int
    practical_periods: int
    credits: float

    is_compulsory: bool
    is_elective: bool
    include_in_result: bool
    include_in_attendance: bool

    status: ClassSubjectStatus
    is_locked: bool

    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    subject: SubjectResponse | None = None

    model_config = ConfigDict(from_attributes=True)
