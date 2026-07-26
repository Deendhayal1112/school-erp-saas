import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.designation.enums import DesignationStatus


class DesignationBase(BaseModel):
    department_id: uuid.UUID = Field(..., description="Department association ID")
    designation_code: str = Field(
        ..., max_length=50, description="Unique designation code identifier"
    )
    designation_name: str = Field(
        ..., max_length=100, description="Designation official title/name"
    )
    display_name: str = Field(
        ...,
        max_length=100,
        description="Display name for user interface representations",
    )
    description: str | None = Field(None, description="Detailed job description")
    employment_category: str = Field(
        ..., max_length=50, description="Category (e.g. Teaching, Non-Teaching, Admin)"
    )
    job_level: str | None = Field(
        None, max_length=50, description="Level (e.g. Junior, Senior, Lead)"
    )
    grade: str | None = Field(
        None, max_length=50, description="Grade assignment reference"
    )
    salary_band: str | None = Field(
        None, max_length=100, description="Salary scale/grade reference band"
    )
    minimum_salary: float = Field(
        0.0, ge=0.0, description="Minimum salary bracket limit"
    )
    maximum_salary: float = Field(
        0.0, ge=0.0, description="Maximum salary bracket limit"
    )
    display_order: int = Field(0, description="Sorting order precedence index")
    is_teaching: bool = Field(
        False, description="Flag indicating academic teaching role status"
    )
    is_management: bool = Field(
        False, description="Flag indicating management executive status"
    )


class DesignationCreate(DesignationBase):
    pass


class DesignationUpdate(BaseModel):
    designation_name: str | None = Field(None, max_length=100)
    display_name: str | None = Field(None, max_length=100)
    description: str | None = None
    employment_category: str | None = Field(None, max_length=50)
    job_level: str | None = Field(None, max_length=50)
    grade: str | None = Field(None, max_length=50)
    salary_band: str | None = Field(None, max_length=100)
    minimum_salary: float | None = Field(None, ge=0.0)
    maximum_salary: float | None = Field(None, ge=0.0)
    display_order: int | None = None
    is_teaching: bool | None = None
    is_management: bool | None = None


class DesignationResponse(DesignationBase):
    id: uuid.UUID
    school_id: uuid.UUID
    status: DesignationStatus
    is_active: bool
    is_locked: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
