import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.class_timetable.enums import TimetableStatus
from app.modules.class_timetable.schemas import (
    ClassTimetableCreate,
    ClassTimetableEntryCreate,
    ClassTimetableEntryResponse,
    ClassTimetableEntryUpdate,
    ClassTimetableResponse,
    ClassTimetableUpdate,
    TimetableCloneRequest,
    WeeklyScheduleResponse,
)
from app.modules.class_timetable.service import ClassTimetableService

router = APIRouter(tags=["Class Timetable"])


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
# CLASS TIMETABLES ENDPOINTS
# ===========================================================================


@router.post(
    "/timetables",
    response_model=CreatedResponse[ClassTimetableResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_timetable(
    data: ClassTimetableCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[ClassTimetableResponse]:
    require_permission(current_user, "class_timetable.create")
    service = ClassTimetableService(db)
    res = await service.create_timetable(current_user.school_id, data, current_user)
    response_data = ClassTimetableResponse.model_validate(res)
    await db.commit()
    return CreatedResponse[ClassTimetableResponse](data=response_data)


@router.get(
    "/timetables",
    response_model=SuccessResponse[list[ClassTimetableResponse]],
)
async def list_timetables(
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    status: TimetableStatus | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("created_at"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[ClassTimetableResponse]]:
    require_permission(current_user, "class_timetable.read")
    service = ClassTimetableService(db)
    res = await service.repo.list_timetables(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        status=status,
        is_active=is_active,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )
    response_data = [ClassTimetableResponse.model_validate(item) for item in res]
    return SuccessResponse[list[ClassTimetableResponse]](data=response_data)


@router.get(
    "/timetables/history",
    response_model=SuccessResponse[list[ClassTimetableResponse]],
)
async def get_version_history(
    class_id: uuid.UUID = Query(...),
    section_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[ClassTimetableResponse]]:
    require_permission(current_user, "class_timetable.read")
    service = ClassTimetableService(db)
    res = await service.repo.get_version_history(
        class_id=class_id,
        section_id=section_id,
        term_id=term_id,
        school_id=current_user.school_id,
    )
    response_data = [ClassTimetableResponse.model_validate(item) for item in res]
    return SuccessResponse[list[ClassTimetableResponse]](data=response_data)


@router.get(
    "/timetables/{id}",
    response_model=SuccessResponse[ClassTimetableResponse],
)
async def get_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ClassTimetableResponse]:
    require_permission(current_user, "class_timetable.read")
    service = ClassTimetableService(db)
    res = await service.get_timetable(id, current_user.school_id)
    response_data = ClassTimetableResponse.model_validate(res)
    return SuccessResponse[ClassTimetableResponse](data=response_data)


@router.put(
    "/timetables/{id}",
    response_model=SuccessResponse[ClassTimetableResponse],
)
async def update_timetable(
    id: uuid.UUID,
    data: ClassTimetableUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ClassTimetableResponse]:
    require_permission(current_user, "class_timetable.update")
    service = ClassTimetableService(db)
    res = await service.update_timetable(id, current_user.school_id, data, current_user)
    response_data = ClassTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[ClassTimetableResponse](data=response_data)


@router.delete(
    "/timetables/{id}",
    response_model=SuccessResponse[None],
)
async def delete_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[None]:
    require_permission(current_user, "class_timetable.delete")
    service = ClassTimetableService(db)
    await service.delete_timetable(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[None](data=None)


# ===========================================================================
# TIMETABLE ENTRIES ENDPOINTS
# ===========================================================================


@router.post(
    "/entries",
    response_model=CreatedResponse[ClassTimetableEntryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_entry(
    data: ClassTimetableEntryCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[ClassTimetableEntryResponse]:
    require_permission(current_user, "class_timetable.update")
    service = ClassTimetableService(db)
    res = await service.add_timetable_entry(current_user.school_id, data, current_user)
    response_data = ClassTimetableEntryResponse.model_validate(res)
    await db.commit()
    return CreatedResponse[ClassTimetableEntryResponse](data=response_data)


@router.get(
    "/entries/{id}",
    response_model=SuccessResponse[ClassTimetableEntryResponse],
)
async def get_entry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ClassTimetableEntryResponse]:
    require_permission(current_user, "class_timetable.read")
    service = ClassTimetableService(db)
    res = await service.get_entry(id, current_user.school_id)
    response_data = ClassTimetableEntryResponse.model_validate(res)
    return SuccessResponse[ClassTimetableEntryResponse](data=response_data)


@router.put(
    "/entries/{id}",
    response_model=SuccessResponse[ClassTimetableEntryResponse],
)
async def update_entry(
    id: uuid.UUID,
    data: ClassTimetableEntryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ClassTimetableEntryResponse]:
    require_permission(current_user, "class_timetable.update")
    service = ClassTimetableService(db)
    res = await service.update_timetable_entry(
        id, current_user.school_id, data, current_user
    )
    response_data = ClassTimetableEntryResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[ClassTimetableEntryResponse](data=response_data)


@router.delete(
    "/entries/{id}",
    response_model=SuccessResponse[None],
)
async def remove_entry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[None]:
    require_permission(current_user, "class_timetable.update")
    service = ClassTimetableService(db)
    await service.remove_timetable_entry(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[None](data=None)


# ===========================================================================
# LIFE CYCLE ACTIONS
# ===========================================================================


@router.post(
    "/timetables/{id}/clone",
    response_model=CreatedResponse[ClassTimetableResponse],
    status_code=status.HTTP_201_CREATED,
)
async def clone_timetable(
    id: uuid.UUID,
    data: TimetableCloneRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[ClassTimetableResponse]:
    require_permission(current_user, "class_timetable.create")
    service = ClassTimetableService(db)
    res = await service.clone_timetable(id, current_user.school_id, data, current_user)
    response_data = ClassTimetableResponse.model_validate(res)
    await db.commit()
    return CreatedResponse[ClassTimetableResponse](data=response_data)


@router.post(
    "/timetables/{id}/publish",
    response_model=SuccessResponse[ClassTimetableResponse],
)
async def publish_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ClassTimetableResponse]:
    require_permission(current_user, "class_timetable.publish")
    service = ClassTimetableService(db)
    res = await service.publish_timetable(id, current_user.school_id, current_user)
    response_data = ClassTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[ClassTimetableResponse](data=response_data)


@router.post(
    "/timetables/{id}/archive",
    response_model=SuccessResponse[ClassTimetableResponse],
)
async def archive_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ClassTimetableResponse]:
    require_permission(current_user, "class_timetable.update")
    service = ClassTimetableService(db)
    res = await service.archive_timetable(id, current_user.school_id, current_user)
    response_data = ClassTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[ClassTimetableResponse](data=response_data)


@router.get(
    "/timetables/{id}/weekly",
    response_model=SuccessResponse[WeeklyScheduleResponse],
)
async def get_weekly_schedule(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[WeeklyScheduleResponse]:
    require_permission(current_user, "class_timetable.read")
    service = ClassTimetableService(db)
    res = await service.generate_weekly_schedule(id, current_user.school_id)
    response_data = WeeklyScheduleResponse.model_validate(res)
    return SuccessResponse[WeeklyScheduleResponse](data=response_data)
