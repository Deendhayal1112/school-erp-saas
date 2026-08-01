import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.timetable_conflict.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
)


class ConflictDetectRequest(BaseModel):
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None


class ConflictDetectResponse(BaseModel):
    total_detected: int
    critical_count: int
    warning_count: int
    message: str


class ResolveConflictRequest(BaseModel):
    resolution_strategy: str = Field(..., examples=["AUTOMATIC", "MANUAL_SWAP", "MANUAL_OVERRIDE"])
    action_taken: str = Field(..., examples=["Reallocated slot to Classroom 102", "Swapped Teacher physics to Jane Doe"])
    alternative_teacher_id: uuid.UUID | None = None
    alternative_room_id: uuid.UUID | None = None
    alternative_working_day_id: uuid.UUID | None = None
    alternative_time_slot_id: uuid.UUID | None = None


class AlternativeSuggestion(BaseModel):
    teacher_id: uuid.UUID | None = None
    teacher_name: str | None = None
    room_id: uuid.UUID | None = None
    room_name: str | None = None
    working_day_id: uuid.UUID | None = None
    day_name: str | None = None
    time_slot_id: uuid.UUID | None = None
    slot_name: str | None = None


class ResolveConflictResponse(BaseModel):
    status: str
    message: str
    suggestions: list[AlternativeSuggestion] | None = None


class ConflictRecordResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    generation_job_id: uuid.UUID | None = None
    conflict_type: ConflictType
    severity: ConflictSeverity
    class_id: uuid.UUID
    section_id: uuid.UUID
    teacher_id: uuid.UUID
    room_id: uuid.UUID | None = None
    subject_id: uuid.UUID
    working_day_id: uuid.UUID
    time_slot_id: uuid.UUID
    description: str
    status: ConflictStatus
    detected_at: datetime.datetime
    resolved_at: datetime.datetime | None = None
    resolved_by: uuid.UUID | None = None
    remarks: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConflictResolutionResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    conflict_record_id: uuid.UUID
    resolution_strategy: str
    action_taken: str
    resolved_by: uuid.UUID
    resolved_at: datetime.datetime
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConflictLogResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    conflict_record_id: uuid.UUID
    action: str
    message: str
    timestamp: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ConflictReportSummary(BaseModel):
    total_conflicts: int
    pending_count: int
    resolved_count: int
    critical_count: int
    warning_count: int


class ConflictReportResponse(BaseModel):
    summary: ConflictReportSummary
    conflicts: list[ConflictRecordResponse]
    generated_at: datetime.datetime
