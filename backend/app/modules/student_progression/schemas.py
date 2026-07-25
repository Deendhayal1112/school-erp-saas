import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.student_progression.enums import ProgressionType


class StudentProgressionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    from_academic_year_id: uuid.UUID | None
    to_academic_year_id: uuid.UUID | None
    from_class_id: uuid.UUID | None
    to_class_id: uuid.UUID | None
    from_section_id: uuid.UUID | None
    to_section_id: uuid.UUID | None
    old_roll_number: str | None
    new_roll_number: str | None
    progression_type: ProgressionType
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class StudentPromotionRequest(BaseModel):
    student_id: uuid.UUID = Field(..., description="Target student UUID to promote")
    to_academic_year_id: uuid.UUID = Field(..., description="Target next academic year")
    to_class_id: uuid.UUID = Field(..., description="Target next class")
    to_section_id: uuid.UUID | None = Field(None, description="Optional target section")
    new_roll_number: str | None = Field(
        None, max_length=20, description="Optional target new roll number"
    )
    remarks: str | None = Field(None, description="Optional remarks annotations")


class BulkPromotionRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="List of student UUIDs to promote"
    )
    to_academic_year_id: uuid.UUID = Field(..., description="Target next academic year")
    to_class_id: uuid.UUID = Field(..., description="Target next class")
    to_section_id: uuid.UUID | None = Field(None, description="Optional target section")
    remarks: str | None = Field(None, description="Optional remarks annotations")


class StudentTransferRequest(BaseModel):
    student_id: uuid.UUID = Field(..., description="Target student to transfer")
    to_academic_year_id: uuid.UUID = Field(
        ..., description="Target target academic year"
    )
    to_class_id: uuid.UUID = Field(..., description="Target target class")
    to_section_id: uuid.UUID | None = Field(None, description="Optional target section")
    remarks: str | None = Field(None, description="Optional remarks annotations")


class StudentGraduationRequest(BaseModel):
    student_id: uuid.UUID = Field(..., description="Target student to graduate")
    remarks: str | None = Field(None, description="Optional remarks annotations")


class AlumniConversionRequest(BaseModel):
    student_id: uuid.UUID = Field(
        ..., description="Target student to convert to alumni"
    )
    remarks: str | None = Field(None, description="Optional remarks annotations")
