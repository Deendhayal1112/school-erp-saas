import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.term.enums import TermStatus


class TermBase(BaseModel):
    name: str = Field(
        ..., min_length=2, max_length=50, description="Term Name (e.g. Semester 1)"
    )
    code: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Term Unique Code (e.g. SEM-1-2026)",
    )
    description: str | None = Field(None, description="Optional description details")
    term_number: int = Field(
        ..., ge=1, description="Sequential number of the term (e.g. 1, 2, 3)"
    )
    start_date: date = Field(..., description="Start date of the term")
    end_date: date = Field(..., description="End date of the term")


class TermCreate(TermBase):
    academic_year_id: uuid.UUID = Field(..., description="Target Academic Year UUID")

    @model_validator(mode="after")
    def validate_dates_order(self) -> "TermCreate":
        if self.end_date <= self.start_date:
            raise ValueError("End Date must be greater than Start Date.")
        return self


class TermUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=50)
    code: str | None = Field(None, min_length=2, max_length=50)
    description: str | None = None
    term_number: int | None = Field(None, ge=1)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates_order(self) -> "TermUpdate":
        s = self.start_date
        e = self.end_date
        if s is not None and e is not None:
            if e <= s:
                raise ValueError("End Date must be greater than Start Date.")
        return self


class TermResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    code: str
    description: str | None
    term_number: int
    start_date: date
    end_date: date
    is_active: bool
    is_default: bool
    is_locked: bool
    status: TermStatus
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
