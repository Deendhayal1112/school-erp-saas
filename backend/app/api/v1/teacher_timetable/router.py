import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.teacher_timetable.enums import (
    TeacherTimetableStatus,
)
from app.modules.teacher_timetable.schemas import (
    TeacherAvailabilityCreate,
    TeacherAvailabilityResponse,
    TeacherTimetableCreate,
    TeacherTimetableResponse,
    TeacherTimetableUpdate,
    TeacherWeeklyScheduleResponse,
)
from app.modules.teacher_timetable.service import TeacherTimetableService

router = APIRouter(tags=["Teacher Timetable"])


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
# TEACHER TIMETABLES ENDPOINTS
# ===========================================================================


@router.post(
    "",
    response_model=CreatedResponse[TeacherTimetableResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_timetable(
    data: TeacherTimetableCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[TeacherTimetableResponse]:
    require_permission(current_user, "teacher_timetable.create")
    service = TeacherTimetableService(db)
    res = await service.create_timetable(current_user.school_id, data, current_user)
    response_data = TeacherTimetableResponse.model_validate(res)
    await db.commit()
    return CreatedResponse[TeacherTimetableResponse](data=response_data)


@router.get(
    "",
    response_model=SuccessResponse[list[TeacherTimetableResponse]],
)
async def list_timetables(
    teacher_id: uuid.UUID | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    working_day_id: uuid.UUID | None = Query(None),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    status: TeacherTimetableStatus | None = Query(None),
    sort_by: str = Query("created_at"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[TeacherTimetableResponse]]:
    require_permission(current_user, "teacher_timetable.read")
    service = TeacherTimetableService(db)
    res = await service.repo.list_timetables(
        school_id=current_user.school_id,
        teacher_id=teacher_id,
        department_id=department_id,
        subject_id=subject_id,
        working_day_id=working_day_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        status=status,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )
    response_data = [TeacherTimetableResponse.model_validate(item) for item in res]
    return SuccessResponse[list[TeacherTimetableResponse]](data=response_data)


@router.get(
    "/history",
    response_model=SuccessResponse[list[TeacherTimetableResponse]],
)
async def get_version_history(
    teacher_id: uuid.UUID = Query(...),
    academic_year_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[TeacherTimetableResponse]]:
    require_permission(current_user, "teacher_timetable.read")
    service = TeacherTimetableService(db)
    res = await service.repo.get_version_history(
        teacher_id=teacher_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        school_id=current_user.school_id,
    )
    response_data = [TeacherTimetableResponse.model_validate(item) for item in res]
    return SuccessResponse[list[TeacherTimetableResponse]](data=response_data)


# ===========================================================================
# TEACHER AVAILABILITY ENDPOINTS
# ===========================================================================


@router.post(
    "/availabilities",
    response_model=SuccessResponse[TeacherAvailabilityResponse],
)
async def update_availability(
    data: TeacherAvailabilityCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherAvailabilityResponse]:
    require_permission(current_user, "teacher_timetable.update")
    service = TeacherTimetableService(db)
    res = await service.update_availability(current_user.school_id, data, current_user)
    response_data = TeacherAvailabilityResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[TeacherAvailabilityResponse](data=response_data)


@router.get(
    "/availabilities",
    response_model=SuccessResponse[list[TeacherAvailabilityResponse]],
)
async def list_availabilities(
    teacher_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[TeacherAvailabilityResponse]]:
    require_permission(current_user, "teacher_timetable.read")
    service = TeacherTimetableService(db)
    res = await service.repo.get_availabilities_by_teacher(
        teacher_id, current_user.school_id
    )
    response_data = [TeacherAvailabilityResponse.model_validate(item) for item in res]
    return SuccessResponse[list[TeacherAvailabilityResponse]](data=response_data)


# ===========================================================================
# DETAIL & WILDCARD ENDPOINTS
# ===========================================================================


@router.get(
    "/{id}",
    response_model=SuccessResponse[TeacherTimetableResponse],
)
async def get_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherTimetableResponse]:
    require_permission(current_user, "teacher_timetable.read")
    service = TeacherTimetableService(db)
    res = await service.get_timetable(id, current_user.school_id)
    response_data = TeacherTimetableResponse.model_validate(res)
    return SuccessResponse[TeacherTimetableResponse](data=response_data)


@router.put(
    "/{id}",
    response_model=SuccessResponse[TeacherTimetableResponse],
)
async def update_timetable(
    id: uuid.UUID,
    data: TeacherTimetableUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherTimetableResponse]:
    require_permission(current_user, "teacher_timetable.update")
    service = TeacherTimetableService(db)
    res = await service.update_timetable(id, current_user.school_id, data, current_user)
    response_data = TeacherTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[TeacherTimetableResponse](data=response_data)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    require_permission(current_user, "teacher_timetable.delete")
    service = TeacherTimetableService(db)
    await service.delete_timetable(id, current_user.school_id, current_user)
    await db.commit()


@router.post(
    "/{id}/sync",
    response_model=SuccessResponse[TeacherTimetableResponse],
)
async def synchronize_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherTimetableResponse]:
    require_permission(current_user, "teacher_timetable.update")
    service = TeacherTimetableService(db)
    res = await service.synchronize_from_class_timetable(
        id, current_user.school_id, current_user
    )
    response_data = TeacherTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[TeacherTimetableResponse](data=response_data)


@router.post(
    "/{id}/publish",
    response_model=SuccessResponse[TeacherTimetableResponse],
)
async def publish_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherTimetableResponse]:
    require_permission(current_user, "teacher_timetable.publish")
    service = TeacherTimetableService(db)
    res = await service.publish_timetable(id, current_user.school_id, current_user)
    response_data = TeacherTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[TeacherTimetableResponse](data=response_data)


@router.post(
    "/{id}/archive",
    response_model=SuccessResponse[TeacherTimetableResponse],
)
async def archive_timetable(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherTimetableResponse]:
    require_permission(current_user, "teacher_timetable.publish")
    service = TeacherTimetableService(db)
    res = await service.archive_timetable(id, current_user.school_id, current_user)
    response_data = TeacherTimetableResponse.model_validate(res)
    await db.commit()
    return SuccessResponse[TeacherTimetableResponse](data=response_data)


@router.get(
    "/{id}/weekly",
    response_model=SuccessResponse[TeacherWeeklyScheduleResponse],
)
async def generate_weekly_schedule(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherWeeklyScheduleResponse]:
    require_permission(current_user, "teacher_timetable.read")
    service = TeacherTimetableService(db)
    res = await service.generate_weekly_schedule(id, current_user.school_id)
    # The return object is already validated as a dict in caching or pydantic model in service layer,
    # converting it to Pydantic and then serialized by FastAPI response_model.
    return SuccessResponse[TeacherWeeklyScheduleResponse](data=res)
