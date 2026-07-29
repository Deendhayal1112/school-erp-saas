import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.experience.enums import (
    EmploymentType,
    ExperienceStatus,
    OrganizationType,
)


class ExperienceBase(BaseModel):
    employment_type: EmploymentType
    organization_name: str = Field(..., min_length=1, max_length=150)
    organization_type: OrganizationType
    designation: str = Field(..., min_length=1, max_length=150)
    department: str | None = Field(None, max_length=150)
    employment_category: str | None = Field(None, max_length=100)
    start_date: date
    end_date: date | None = None
    currently_working: bool = False
    experience_years: int | None = Field(0, ge=0)
    experience_months: int | None = Field(0, ge=0, le=11)
    salary: float | None = Field(None, ge=0.0)
    currency: str | None = Field("INR", max_length=10)
    reason_for_leaving: str | None = None
    responsibilities: str | None = None
    achievements: str | None = None
    skills_used: str | None = None
    manager_name: str | None = Field(None, max_length=150)
    manager_email: str | None = Field(None, max_length=150)
    manager_phone: str | None = Field(None, max_length=50)
    reference_available: bool = False
    experience_certificate_url: str | None = Field(None, max_length=255)
    remarks: str | None = None


class ExperienceCreate(ExperienceBase):
    employee_id: uuid.UUID


class ExperienceUpdate(BaseModel):
    employment_type: EmploymentType | None = None
    organization_name: str | None = Field(None, min_length=1, max_length=150)
    organization_type: OrganizationType | None = None
    designation: str | None = Field(None, min_length=1, max_length=150)
    department: str | None = Field(None, max_length=150)
    employment_category: str | None = Field(None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    currently_working: bool | None = None
    experience_years: int | None = Field(None, ge=0)
    experience_months: int | None = Field(None, ge=0, le=11)
    salary: float | None = Field(None, ge=0.0)
    currency: str | None = Field(None, max_length=10)
    reason_for_leaving: str | None = None
    responsibilities: str | None = None
    achievements: str | None = None
    skills_used: str | None = None
    manager_name: str | None = Field(None, max_length=150)
    manager_email: str | None = Field(None, max_length=150)
    manager_phone: str | None = Field(None, max_length=50)
    reference_available: bool | None = None
    experience_certificate_url: str | None = Field(None, max_length=255)
    remarks: str | None = None


class ExperienceResponse(ExperienceBase):
    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    is_verified: bool
    verification_date: datetime | None
    verification_by: uuid.UUID | None
    status: ExperienceStatus
    is_active: bool
    is_locked: bool
    is_deleted: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
