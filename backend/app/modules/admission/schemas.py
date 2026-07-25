import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.admission.enums import AdmissionStatus
from app.modules.admission.validators import validate_academic_year


class AdmissionBase(BaseModel):
    academic_year: str = Field(
        ..., description="Academic year (format YYYY-YYYY, e.g. 2026-2027)."
    )
    class_id: uuid.UUID = Field(..., description="Target class UUID.")
    section_id: uuid.UUID | None = Field(
        None, description="Optional target section UUID."
    )
    admission_date: date | None = Field(None, description="Formal admission date.")
    application_date: date = Field(
        default_factory=date.today, description="Application submission date."
    )
    remarks: str | None = Field(None, description="Optional remarks/comments.")
    documents_verified: bool = Field(
        False, description="Flag indicating if all documents have been verified."
    )
    fees_paid: bool = Field(
        False, description="Flag indicating if the admission fee has been paid."
    )


class AdmissionCreate(AdmissionBase):
    student_id: uuid.UUID = Field(..., description="Student profile UUID.")

    @field_validator("academic_year")
    @classmethod
    def validate_ac_year(cls, v: str) -> str:
        return validate_academic_year(v)


class AdmissionUpdate(BaseModel):
    academic_year: str | None = Field(None)
    class_id: uuid.UUID | None = Field(None)
    section_id: uuid.UUID | None = Field(None)
    admission_date: date | None = Field(None)
    application_date: date | None = Field(None)
    remarks: str | None = Field(None)
    documents_verified: bool | None = Field(None)
    fees_paid: bool | None = Field(None)

    @field_validator("academic_year")
    @classmethod
    def validate_ac_year(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_academic_year(v)
        return v


class AdmissionTimelineResponse(BaseModel):
    id: uuid.UUID
    admission_id: uuid.UUID
    from_status: AdmissionStatus
    to_status: AdmissionStatus
    action_by: uuid.UUID | None
    remarks: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdmissionResponse(AdmissionBase):
    id: uuid.UUID
    school_id: uuid.UUID
    application_number: str
    student_id: uuid.UUID
    status: AdmissionStatus
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejected_by: uuid.UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    timeline: list[AdmissionTimelineResponse] | None = None

    model_config = ConfigDict(from_attributes=True)


class AdmissionActionRequest(BaseModel):
    remarks: str | None = Field(None, description="Optional transition log remarks.")


class AdmissionRejectRequest(BaseModel):
    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Required rejection reason explanation.",
    )
    remarks: str | None = Field(None, description="Optional transition log remarks.")
