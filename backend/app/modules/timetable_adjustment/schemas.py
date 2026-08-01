"""
Pydantic v2 schemas for Timetable Adjustments & Teacher Substitution API.
"""

import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.timetable_adjustment.enums import (
    AdjustmentStatus,
    AdjustmentType,
    SubstitutionStatus,
    SubstitutionType,
)


# ---------------------------------------------------------------------------
# Timetable Adjustment Schemas
# ---------------------------------------------------------------------------

class TimetableAdjustmentCreate(BaseModel):
    """Request body for creating a new timetable adjustment."""

    class_timetable_entry_id: uuid.UUID = Field(..., description="ID of the timetable entry to adjust.")
    adjustment_type: AdjustmentType
    reason: str = Field(..., min_length=5, max_length=500)

    # Optional new values — at least one must be provided
    new_teacher_id: uuid.UUID | None = None
    new_room_id: uuid.UUID | None = None
    new_time_slot_id: uuid.UUID | None = None
    new_working_day_id: uuid.UUID | None = None

    effective_date: datetime.date
    expiry_date: datetime.date | None = None
    is_recurring: bool = False
    remarks: str | None = None


class TimetableAdjustmentUpdate(BaseModel):
    """Request body for updating a PENDING adjustment."""

    reason: str | None = Field(None, min_length=5, max_length=500)
    new_teacher_id: uuid.UUID | None = None
    new_room_id: uuid.UUID | None = None
    new_time_slot_id: uuid.UUID | None = None
    new_working_day_id: uuid.UUID | None = None
    effective_date: datetime.date | None = None
    expiry_date: datetime.date | None = None
    is_recurring: bool | None = None
    remarks: str | None = None


class ApproveAdjustmentRequest(BaseModel):
    """Request body for approving or rejecting an adjustment."""

    remarks: str | None = None


class RejectAdjustmentRequest(BaseModel):
    """Request body for rejecting an adjustment."""

    remarks: str = Field(..., min_length=5, description="Reason for rejection.")


class AdjustmentHistoryResponse(BaseModel):
    id: uuid.UUID
    adjustment_id: uuid.UUID
    from_status: str
    to_status: str
    action: str
    actor_id: uuid.UUID | None = None
    notes: str | None = None
    changed_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TimetableAdjustmentResponse(BaseModel):
    """Full response for a timetable adjustment record."""

    id: uuid.UUID
    school_id: uuid.UUID
    class_timetable_entry_id: uuid.UUID
    adjustment_type: AdjustmentType
    reason: str
    old_teacher_id: uuid.UUID | None = None
    new_teacher_id: uuid.UUID | None = None
    old_room_id: uuid.UUID | None = None
    new_room_id: uuid.UUID | None = None
    old_time_slot_id: uuid.UUID | None = None
    new_time_slot_id: uuid.UUID | None = None
    old_working_day_id: uuid.UUID | None = None
    new_working_day_id: uuid.UUID | None = None
    effective_date: datetime.date
    expiry_date: datetime.date | None = None
    is_recurring: bool
    status: AdjustmentStatus
    approved_by: uuid.UUID | None = None
    approved_at: datetime.datetime | None = None
    remarks: str | None = None
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Teacher Substitution Schemas
# ---------------------------------------------------------------------------

class TeacherSubstitutionCreate(BaseModel):
    """Request body for creating a new teacher substitution."""

    original_teacher_id: uuid.UUID
    substitute_teacher_id: uuid.UUID
    class_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    working_day_id: uuid.UUID
    time_slot_id: uuid.UUID
    reason: str = Field(..., min_length=5, max_length=500)
    substitution_type: SubstitutionType = SubstitutionType.PLANNED
    effective_date: datetime.date
    remarks: str | None = None


class ApproveSubstitutionRequest(BaseModel):
    """Request body for approving a teacher substitution."""

    remarks: str | None = None


class RejectSubstitutionRequest(BaseModel):
    """Request body for rejecting a teacher substitution."""

    remarks: str = Field(..., min_length=5, description="Reason for rejection.")


class SubstitutionHistoryResponse(BaseModel):
    id: uuid.UUID
    substitution_id: uuid.UUID
    from_status: str
    to_status: str
    action: str
    actor_id: uuid.UUID | None = None
    notes: str | None = None
    changed_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TeacherSubstitutionResponse(BaseModel):
    """Full response for a teacher substitution record."""

    id: uuid.UUID
    school_id: uuid.UUID
    original_teacher_id: uuid.UUID
    substitute_teacher_id: uuid.UUID
    class_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    working_day_id: uuid.UUID
    time_slot_id: uuid.UUID
    reason: str
    substitution_type: SubstitutionType
    effective_date: datetime.date
    status: SubstitutionStatus
    approved_by: uuid.UUID | None = None
    approved_at: datetime.datetime | None = None
    remarks: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Substitution Engine Output
# ---------------------------------------------------------------------------

class SubstituteSuggestion(BaseModel):
    """An available substitute teacher suggestion from the engine."""

    teacher_id: uuid.UUID
    teacher_name: str
    department: str | None = None
    weekly_load: int
    remaining_capacity: int
    is_qualified: bool
    suggestion_rank: int = Field(..., description="Lower is better.")
    metadata: dict[str, Any] | None = None


class SubstitutionSuggestionsResponse(BaseModel):
    """Response containing ranked substitute suggestions."""

    suggestions: list[SubstituteSuggestion]
    total_found: int
    message: str


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class AdjustmentSummaryResponse(BaseModel):
    """Aggregated summary for pending/approved adjustments."""

    total: int
    pending: int
    approved: int
    applied: int
    rejected: int
    rolled_back: int
