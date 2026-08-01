"""
REST API router for Timetable Adjustments & Teacher Substitution.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import (
    CreatedResponse,
    DeletedResponse,
    PaginatedResponse,
    PaginationMetadata,
    UpdatedResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.timetable_adjustment.enums import AdjustmentStatus, SubstitutionStatus
from app.modules.timetable_adjustment.schemas import (
    AdjustmentHistoryResponse,
    AdjustmentSummaryResponse,
    ApproveAdjustmentRequest,
    ApproveSubstitutionRequest,
    RejectAdjustmentRequest,
    RejectSubstitutionRequest,
    SubstitutionHistoryResponse,
    SubstitutionSuggestionsResponse,
    TeacherSubstitutionCreate,
    TeacherSubstitutionResponse,
    TimetableAdjustmentCreate,
    TimetableAdjustmentResponse,
    TimetableAdjustmentUpdate,
)
from app.modules.timetable_adjustment.service import (
    TeacherSubstitutionService,
    TimetableAdjustmentService,
)
from app.modules.timetable_adjustment.repository import (
    TimetableAdjustmentRepository,
    TeacherSubstitutionRepository,
)

from app.schemas.response import SuccessResponse

router = APIRouter(tags=["Timetable Adjustments & Teacher Substitution"])


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


# ===========================================================================
# Timetable Adjustment Endpoints
# ===========================================================================


@router.post(
    "/adjustments",
    response_model=CreatedResponse[TimetableAdjustmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a timetable adjustment",
)
async def create_adjustment(
    payload: TimetableAdjustmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.create")
    svc = TimetableAdjustmentService(db)
    result = await svc.create_adjustment(current_user.school_id, payload, current_user.id)
    return CreatedResponse[TimetableAdjustmentResponse](
        message="Timetable adjustment created successfully.", data=result
    )


@router.get(
    "/adjustments",
    response_model=PaginatedResponse[TimetableAdjustmentResponse],
    summary="List timetable adjustments",
)
async def list_adjustments(
    status: AdjustmentStatus | None = Query(None, description="Filter by status."),
    entry_id: uuid.UUID | None = Query(None, description="Filter by timetable entry ID."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.read")
    svc = TimetableAdjustmentService(db)
    results, total = await svc.list_adjustments(
        school_id=current_user.school_id,
        status=status,
        entry_id=entry_id,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, -(-total // page_size))
    return PaginatedResponse[TimetableAdjustmentResponse](
        message="Adjustments retrieved successfully.",
        pagination=PaginationMetadata(
            total_records=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            next=None,
            previous=None,
        ),
        results=results,
    )


@router.get(
    "/adjustments/summary",
    response_model=SuccessResponse[AdjustmentSummaryResponse],
    summary="Get adjustment summary counts by status",
)
async def get_adjustment_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[AdjustmentSummaryResponse]:
    require_permission(current_user, "timetable.adjustment.read")
    svc = TimetableAdjustmentService(db)
    result = await svc.get_summary(current_user.school_id)
    return SuccessResponse[AdjustmentSummaryResponse](data=result)


@router.get(
    "/adjustments/{adjustment_id}",
    response_model=SuccessResponse[TimetableAdjustmentResponse],
    summary="Get a single timetable adjustment",
)
async def get_adjustment(
    adjustment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.read")
    svc = TimetableAdjustmentService(db)
    result = await svc.get_adjustment(current_user.school_id, adjustment_id)
    return SuccessResponse[TimetableAdjustmentResponse](data=result)


@router.put(
    "/adjustments/{adjustment_id}",
    response_model=UpdatedResponse[TimetableAdjustmentResponse],
    summary="Update a PENDING timetable adjustment",
)
async def update_adjustment(
    adjustment_id: uuid.UUID,
    payload: TimetableAdjustmentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UpdatedResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.update")
    svc = TimetableAdjustmentService(db)
    result = await svc.update_adjustment(
        current_user.school_id, adjustment_id, payload, current_user.id
    )
    return UpdatedResponse[TimetableAdjustmentResponse](
        message="Adjustment updated successfully.", data=result
    )


@router.delete(
    "/adjustments/{adjustment_id}",
    response_model=DeletedResponse,
    summary="Delete a PENDING timetable adjustment",
)
async def delete_adjustment(
    adjustment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DeletedResponse:
    require_permission(current_user, "timetable.adjustment.update")
    svc = TimetableAdjustmentService(db)
    await svc.delete_adjustment(current_user.school_id, adjustment_id, current_user.id)
    return DeletedResponse(message="Adjustment deleted successfully.")


@router.post(
    "/adjustments/{adjustment_id}/approve",
    response_model=SuccessResponse[TimetableAdjustmentResponse],
    summary="Approve a PENDING timetable adjustment",
)
async def approve_adjustment(
    adjustment_id: uuid.UUID,
    payload: ApproveAdjustmentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.approve")
    svc = TimetableAdjustmentService(db)
    result = await svc.approve_adjustment(
        current_user.school_id, adjustment_id, current_user.id, payload.remarks
    )
    return SuccessResponse[TimetableAdjustmentResponse](
        message="Adjustment approved successfully.", data=result
    )


@router.post(
    "/adjustments/{adjustment_id}/reject",
    response_model=SuccessResponse[TimetableAdjustmentResponse],
    summary="Reject a PENDING timetable adjustment",
)
async def reject_adjustment(
    adjustment_id: uuid.UUID,
    payload: RejectAdjustmentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.approve")
    svc = TimetableAdjustmentService(db)
    result = await svc.reject_adjustment(
        current_user.school_id, adjustment_id, current_user.id, payload.remarks
    )
    return SuccessResponse[TimetableAdjustmentResponse](
        message="Adjustment rejected.", data=result
    )


@router.post(
    "/adjustments/{adjustment_id}/apply",
    response_model=SuccessResponse[TimetableAdjustmentResponse],
    summary="Apply an APPROVED adjustment to the live timetable entry",
)
async def apply_adjustment(
    adjustment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.approve")
    svc = TimetableAdjustmentService(db)
    result = await svc.apply_adjustment(
        current_user.school_id, adjustment_id, current_user.id
    )
    return SuccessResponse[TimetableAdjustmentResponse](
        message="Adjustment applied to timetable.", data=result
    )


@router.post(
    "/adjustments/{adjustment_id}/rollback",
    response_model=SuccessResponse[TimetableAdjustmentResponse],
    summary="Roll back an APPLIED timetable adjustment",
)
async def rollback_adjustment(
    adjustment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimetableAdjustmentResponse]:
    require_permission(current_user, "timetable.adjustment.approve")
    svc = TimetableAdjustmentService(db)
    result = await svc.rollback_adjustment(
        current_user.school_id, adjustment_id, current_user.id
    )
    return SuccessResponse[TimetableAdjustmentResponse](
        message="Adjustment rolled back.", data=result
    )


@router.get(
    "/adjustments/{adjustment_id}/history",
    response_model=SuccessResponse[list[AdjustmentHistoryResponse]],
    summary="Get workflow history for a timetable adjustment",
)
async def get_adjustment_history(
    adjustment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[AdjustmentHistoryResponse]]:
    require_permission(current_user, "timetable.adjustment.read")
    repo = TimetableAdjustmentRepository(db)
    history = await repo.get_history(adjustment_id, current_user.school_id)
    data = [AdjustmentHistoryResponse.model_validate(h) for h in history]
    return SuccessResponse[list[AdjustmentHistoryResponse]](data=data)


# ===========================================================================
# Teacher Substitution Endpoints
# ===========================================================================


@router.post(
    "/substitutions",
    response_model=CreatedResponse[TeacherSubstitutionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a teacher substitution",
)
async def create_substitution(
    payload: TeacherSubstitutionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[TeacherSubstitutionResponse]:
    require_permission(current_user, "teacher.substitution.create")
    svc = TeacherSubstitutionService(db)
    result = await svc.create_substitution(current_user.school_id, payload, current_user.id)
    return CreatedResponse[TeacherSubstitutionResponse](
        message="Teacher substitution created successfully.", data=result
    )


@router.get(
    "/substitutions",
    response_model=PaginatedResponse[TeacherSubstitutionResponse],
    summary="List teacher substitutions",
)
async def list_substitutions(
    status: SubstitutionStatus | None = Query(None, description="Filter by status."),
    original_teacher_id: uuid.UUID | None = Query(None),
    substitute_teacher_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TeacherSubstitutionResponse]:
    require_permission(current_user, "teacher.substitution.read")
    svc = TeacherSubstitutionService(db)
    results, total = await svc.list_substitutions(
        school_id=current_user.school_id,
        status=status,
        original_teacher_id=original_teacher_id,
        substitute_teacher_id=substitute_teacher_id,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, -(-total // page_size))
    return PaginatedResponse[TeacherSubstitutionResponse](
        message="Substitutions retrieved successfully.",
        pagination=PaginationMetadata(
            total_records=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            next=None,
            previous=None,
        ),
        results=results,
    )


@router.get(
    "/substitutions/suggestions",
    response_model=SuccessResponse[SubstitutionSuggestionsResponse],
    summary="Get ranked substitute teacher suggestions",
)
async def get_substitute_suggestions(
    subject_id: uuid.UUID = Query(...),
    working_day_id: uuid.UUID = Query(...),
    time_slot_id: uuid.UUID = Query(...),
    original_teacher_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[SubstitutionSuggestionsResponse]:
    require_permission(current_user, "teacher.substitution.read")
    svc = TeacherSubstitutionService(db)
    result = await svc.get_substitute_suggestions(
        school_id=current_user.school_id,
        subject_id=subject_id,
        working_day_id=working_day_id,
        time_slot_id=time_slot_id,
        original_teacher_id=original_teacher_id,
    )
    return SuccessResponse[SubstitutionSuggestionsResponse](data=result)


@router.get(
    "/substitutions/{substitution_id}",
    response_model=SuccessResponse[TeacherSubstitutionResponse],
    summary="Get a single teacher substitution",
)
async def get_substitution(
    substitution_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherSubstitutionResponse]:
    require_permission(current_user, "teacher.substitution.read")
    svc = TeacherSubstitutionService(db)
    result = await svc.get_substitution(current_user.school_id, substitution_id)
    return SuccessResponse[TeacherSubstitutionResponse](data=result)


@router.post(
    "/substitutions/{substitution_id}/approve",
    response_model=SuccessResponse[TeacherSubstitutionResponse],
    summary="Approve a PENDING teacher substitution",
)
async def approve_substitution(
    substitution_id: uuid.UUID,
    payload: ApproveSubstitutionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherSubstitutionResponse]:
    require_permission(current_user, "teacher.substitution.approve")
    svc = TeacherSubstitutionService(db)
    result = await svc.approve_substitution(
        current_user.school_id, substitution_id, current_user.id, payload.remarks
    )
    return SuccessResponse[TeacherSubstitutionResponse](
        message="Substitution approved.", data=result
    )


@router.post(
    "/substitutions/{substitution_id}/reject",
    response_model=SuccessResponse[TeacherSubstitutionResponse],
    summary="Reject a PENDING teacher substitution",
)
async def reject_substitution(
    substitution_id: uuid.UUID,
    payload: RejectSubstitutionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherSubstitutionResponse]:
    require_permission(current_user, "teacher.substitution.approve")
    svc = TeacherSubstitutionService(db)
    result = await svc.reject_substitution(
        current_user.school_id, substitution_id, current_user.id, payload.remarks
    )
    return SuccessResponse[TeacherSubstitutionResponse](
        message="Substitution rejected.", data=result
    )


@router.get(
    "/substitutions/{substitution_id}/history",
    response_model=SuccessResponse[list[SubstitutionHistoryResponse]],
    summary="Get workflow history for a teacher substitution",
)
async def get_substitution_history(
    substitution_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[SubstitutionHistoryResponse]]:
    require_permission(current_user, "teacher.substitution.read")
    repo = TeacherSubstitutionRepository(db)
    history = await repo.get_history(substitution_id, current_user.school_id)
    data = [SubstitutionHistoryResponse.model_validate(h) for h in history]
    return SuccessResponse[list[SubstitutionHistoryResponse]](data=data)
