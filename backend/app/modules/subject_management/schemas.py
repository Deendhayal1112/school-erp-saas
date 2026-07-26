import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.subject_management.enums import SubjectStatus, SubjectType


class SubjectBase(BaseModel):
    subject_code: str = Field(
        ..., min_length=1, max_length=50, description="Unique Subject Code"
    )
    subject_name: str = Field(
        ..., min_length=1, max_length=100, description="Unique Subject Name"
    )
    short_name: str = Field(
        ..., min_length=1, max_length=20, description="Short name / abbreviation"
    )
    display_name: str = Field(
        ..., min_length=1, max_length=100, description="Display Name"
    )
    description: str | None = Field(None, description="Detailed description")

    subject_type: SubjectType = Field(default=SubjectType.CORE)
    category: str = Field(
        ..., min_length=1, max_length=50, description="Science, Arts, Language, etc."
    )
    credits: float = Field(default=0.0, ge=0.0)

    weekly_periods: int = Field(default=1, ge=1)
    theory_hours: int = Field(default=0, ge=0)
    practical_hours: int = Field(default=0, ge=0)

    passing_marks: int = Field(default=0, ge=0)
    maximum_marks: int = Field(default=100, ge=1)

    language: str | None = Field(None, max_length=50)

    is_core: bool = Field(default=True)
    is_elective: bool = Field(default=False)
    has_practical: bool = Field(default=False)

    display_order: int = Field(default=0, ge=0)


class SubjectCreate(SubjectBase):
    @model_validator(mode="after")
    def validate_create_fields(self) -> "SubjectCreate":
        if self.maximum_marks <= self.passing_marks:
            raise ValueError(
                "Maximum Marks must be strictly greater than Passing Marks."
            )

        if self.subject_type == SubjectType.LANGUAGE and not self.language:
            raise ValueError("Language subjects must specify the target language.")

        if (
            self.subject_type == SubjectType.LAB or self.has_practical
        ) and self.practical_hours <= 0:
            raise ValueError(
                "Lab and practical-enabled subjects must have practical hours greater than 0."
            )

        if self.is_core and self.is_elective:
            raise ValueError("A subject cannot be both a Core and an Elective subject.")

        if self.subject_type == SubjectType.ELECTIVE:
            if self.is_core:
                raise ValueError(
                    "Elective subject types cannot have the 'is_core' flag set to True."
                )
            if not self.is_elective:
                raise ValueError(
                    "Elective subject types must have 'is_elective' set to True."
                )

        return self


class SubjectUpdate(BaseModel):
    subject_code: str | None = Field(None, min_length=1, max_length=50)
    subject_name: str | None = Field(None, min_length=1, max_length=100)
    short_name: str | None = Field(None, min_length=1, max_length=20)
    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None

    subject_type: SubjectType | None = None
    category: str | None = Field(None, min_length=1, max_length=50)
    credits: float | None = Field(None, ge=0.0)

    weekly_periods: int | None = Field(None, ge=1)
    theory_hours: int | None = Field(None, ge=0)
    practical_hours: int | None = Field(None, ge=0)

    passing_marks: int | None = Field(None, ge=0)
    maximum_marks: int | None = Field(None, ge=1)

    language: str | None = Field(None, max_length=50)

    is_core: bool | None = None
    is_elective: bool | None = None
    has_practical: bool | None = None

    display_order: int | None = Field(None, ge=0)


class SubjectResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    subject_code: str
    subject_name: str
    short_name: str
    display_name: str
    description: str | None

    subject_type: SubjectType
    category: str
    credits: float

    weekly_periods: int
    theory_hours: int
    practical_hours: int

    passing_marks: int
    maximum_marks: int

    language: str | None

    is_core: bool
    is_elective: bool
    has_practical: bool

    display_order: int
    status: SubjectStatus
    is_locked: bool

    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
