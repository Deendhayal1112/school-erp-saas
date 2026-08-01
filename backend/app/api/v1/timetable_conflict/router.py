import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.timetable_conflict.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
)
from app.modules.timetable_conflict.schemas import (
    ConflictDetectRequest,
    ConflictDetectResponse,
    ConflictRecordResponse,
    ConflictReportResponse,
    ResolveConflictRequest,
    ResolveConflictResponse,
)
from app.modules.timetable_conflict.service import TimetableConflictService

router = APIRouter(tags=["Timetable Conflict Management"])


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


@router.post(
    "/detect",
    response_model=CreatedResponse[ConflictDetectResponse],
    status_code=status.HTTP_201_CREATED,
)
async def detect_conflicts(
    data: ConflictDetectRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[ConflictDetectResponse]:
    require_permission(current_user, "timetable_conflict.manage")
    service = TimetableConflictService(db)
    res = await service.detect_and_record_conflicts(current_user.school_id, data, current_user)
    return CreatedResponse[ConflictDetectResponse](data=res)


@router.get(
    "/report",
    response_model=SuccessResponse[ConflictReportResponse],
)
async def get_conflict_report(
    academic_year_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ConflictReportResponse]:
    require_permission(current_user, "timetable_conflict.read")
    service = TimetableConflictService(db)
    res = await service.get_conflict_report(current_user.school_id, academic_year_id, term_id)
    return SuccessResponse[ConflictReportResponse](data=res)


@router.get(
    "",
    response_model=SuccessResponse[list[ConflictRecordResponse]],
)
async def list_conflicts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    conflict_type: ConflictType | None = Query(None),
    severity: ConflictSeverity | None = Query(None),
    teacher_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    status: ConflictStatus | None = Query(None),
    sort_by: str = Query("detected_at", regex="^(detected_at|severity)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[ConflictRecordResponse]]:
    require_permission(current_user, "timetable_conflict.read")
    service = TimetableConflictService(db)
    records = await service.repo.list_conflicts(
        school_id=current_user.school_id,
        skip=skip,
        limit=limit,
        conflict_type=conflict_type,
        severity=severity,
        teacher_id=teacher_id,
        room_id=room_id,
        class_id=class_id,
        section_id=section_id,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    resp_data = [ConflictRecordResponse.model_validate(item) for item in records]
    return SuccessResponse[list[ConflictRecordResponse]](data=resp_data)


@router.get(
    "/{id}",
    response_model=SuccessResponse[ConflictRecordResponse],
)
async def get_conflict(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ConflictRecordResponse]:
    require_permission(current_user, "timetable_conflict.read")
    service = TimetableConflictService(db)
    record = await service.get_conflict(id, current_user.school_id)
    resp_data = ConflictRecordResponse.model_validate(record)
    return SuccessResponse[ConflictRecordResponse](data=resp_data)


@router.post(
    "/{id}/resolve",
    response_model=SuccessResponse[ResolveConflictResponse],
)
async def resolve_conflict(
    id: uuid.UUID,
    data: ResolveConflictRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ResolveConflictResponse]:
    require_permission(current_user, "timetable_conflict.resolve")
    service = TimetableConflictService(db)
    res = await service.resolve_conflict(id, current_user.school_id, data, current_user)
    return SuccessResponse[ResolveConflictResponse](data=res)


@router.post(
    "/{id}/retry",
    response_model=SuccessResponse[ResolveConflictResponse],
)
async def retry_resolution(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ResolveConflictResponse]:
    require_permission(current_user, "timetable_conflict.resolve")
    service = TimetableConflictService(db)
    res = await service.retry_resolution(id, current_user.school_id, current_user)
    return SuccessResponse[ResolveConflictResponse](data=res)
