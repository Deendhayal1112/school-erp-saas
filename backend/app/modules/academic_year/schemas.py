import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.academic_year.enums import AcademicYearStatus


class AcademicYearBase(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Academic Year Name (e.g. 2026-2027)",
    )
    code: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Academic Year Unique Code (e.g. AY2627)",
    )
    start_date: date = Field(..., description="Start date of the academic year")
    end_date: date = Field(..., description="End date of the academic year")
    description: str | None = Field(None, description="Optional description details")


class AcademicYearCreate(AcademicYearBase):
    @model_validator(mode="after")
    def validate_dates_order(self) -> "AcademicYearCreate":
        if self.end_date <= self.start_date:
            raise ValueError("End Date must be greater than Start Date.")
        return self


class AcademicYearUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=50)
    code: str | None = Field(None, min_length=2, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_dates_order(self) -> "AcademicYearUpdate":
        s = self.start_date
        e = self.end_date
        if s is not None and e is not None:
            if e <= s:
                raise ValueError("End Date must be greater than Start Date.")
        return self


class AcademicYearResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    code: str
    start_date: date
    end_date: date
    description: str | None
    is_active: bool
    is_default: bool
    is_locked: bool
    status: AcademicYearStatus
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
