import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.timetable_generator.enums import (
    JobStatus,
    ResultStatus,
)


class GenerateTimetableRequest(BaseModel):
    academic_year_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    term_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    job_name: str = Field(..., max_length=100, examples=["Auto Gen Term 1 Fall"])


class GenerateTimetableResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    job_name: str
    message: str


class ValidationRequest(BaseModel):
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None


class ConstraintViolation(BaseModel):
    constraint_type: str  # HARD or SOFT
    rule_name: str
    message: str
    entity_details: dict[str, Any] | None = None


class ValidationResponse(BaseModel):
    is_valid: bool
    violations: list[ConstraintViolation]


class GenerationJobResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    job_name: str
    status: JobStatus
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    execution_time: float | None = None
    total_classes: int
    total_teachers: int
    total_subjects: int
    generated_entries: int
    failed_entries: int
    remarks: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GenerationResultResponse(BaseModel):
    id: uuid.UUID
    generation_job_id: uuid.UUID
    school_id: uuid.UUID
    timetable_id: uuid.UUID | None = None
    status: ResultStatus
    score: float
    data: dict[str, Any]
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GenerationLogResponse(BaseModel):
    id: uuid.UUID
    generation_job_id: uuid.UUID
    school_id: uuid.UUID
    log_level: str
    message: str
    timestamp: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
