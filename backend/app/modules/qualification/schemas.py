import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.qualification.enums import (
    ModeOfStudy,
    QualificationStatus,
    QualificationType,
)


class QualificationBase(BaseModel):
    qualification_type: QualificationType
    qualification_name: str = Field(..., min_length=1, max_length=150)
    degree: str | None = Field(None, max_length=150)
    specialization: str | None = Field(None, max_length=150)
    institution_name: str = Field(..., min_length=1, max_length=200)
    board_or_university: str | None = Field(None, max_length=200)
    country: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    mode_of_study: ModeOfStudy = ModeOfStudy.FULL_TIME
    grade: str | None = Field(None, max_length=20)
    percentage: float | None = Field(None, ge=0.0, le=100.0)
    cgpa: float | None = Field(None, ge=0.0)
    cgpa_scale: float | None = Field(None, gt=0.0)
    passing_year: int | None = Field(None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    certificate_number: str | None = Field(None, max_length=100)
    issuing_authority: str | None = Field(None, max_length=150)
    license_number: str | None = Field(None, max_length=100)
    valid_from: date | None = None
    valid_until: date | None = None
    is_highest_qualification: bool = False
    document_url: str | None = Field(None, max_length=255)
    remarks: str | None = None


class QualificationCreate(QualificationBase):
    employee_id: uuid.UUID


class QualificationUpdate(BaseModel):
    qualification_type: QualificationType | None = None
    qualification_name: str | None = Field(None, min_length=1, max_length=150)
    degree: str | None = Field(None, max_length=150)
    specialization: str | None = Field(None, max_length=150)
    institution_name: str | None = Field(None, min_length=1, max_length=200)
    board_or_university: str | None = Field(None, max_length=200)
    country: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)
    mode_of_study: ModeOfStudy | None = None
    grade: str | None = Field(None, max_length=20)
    percentage: float | None = Field(None, ge=0.0, le=100.0)
    cgpa: float | None = Field(None, ge=0.0)
    cgpa_scale: float | None = Field(None, gt=0.0)
    passing_year: int | None = Field(None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    certificate_number: str | None = Field(None, max_length=100)
    issuing_authority: str | None = Field(None, max_length=150)
    license_number: str | None = Field(None, max_length=100)
    valid_from: date | None = None
    valid_until: date | None = None
    is_highest_qualification: bool | None = None
    document_url: str | None = Field(None, max_length=255)
    remarks: str | None = None


class QualificationResponse(QualificationBase):
    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    is_verified: bool
    verification_date: datetime | None
    verification_by: uuid.UUID | None
    status: QualificationStatus
    is_active: bool
    is_locked: bool
    is_deleted: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
