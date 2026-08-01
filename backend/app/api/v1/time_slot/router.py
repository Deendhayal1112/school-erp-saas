import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.time_slot.schemas import (
    BreakPeriodCreate,
    BreakPeriodResponse,
    BreakPeriodUpdate,
    PeriodCreate,
    PeriodResponse,
    PeriodUpdate,
    TimeSlotCreate,
    TimeSlotResponse,
    TimeSlotUpdate,
)
from app.modules.time_slot.service import TimeSlotService

router = APIRouter(tags=["Time Slots & Periods"])


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
# TIME SLOTS ENDPOINTS
# ===========================================================================


@router.post(
    "/time-slots",
    response_model=CreatedResponse[TimeSlotResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_time_slot(
    data: TimeSlotCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[TimeSlotResponse]:
    require_permission(current_user, "timeslot.create")
    service = TimeSlotService(db)
    res = await service.create_time_slot(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[TimeSlotResponse](data=res)


@router.get(
    "/time-slots",
    response_model=SuccessResponse[list[TimeSlotResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_time_slots(
    academic_year_id: uuid.UUID | None = Query(None),
    working_day_id: uuid.UUID | None = Query(None),
    slot_type: str | None = Query(None),
    is_break: bool | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("display_order"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[TimeSlotResponse]]:
    require_permission(current_user, "timeslot.read")
    service = TimeSlotService(db)
    res = await service.list_time_slots(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        working_day_id=working_day_id,
        slot_type=slot_type,
        is_break=is_break,
        is_active=is_active,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[TimeSlotResponse]](data=list(res))


@router.get(
    "/time-slots/{id}",
    response_model=SuccessResponse[TimeSlotResponse],
    status_code=status.HTTP_200_OK,
)
async def get_time_slot(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimeSlotResponse]:
    require_permission(current_user, "timeslot.read")
    service = TimeSlotService(db)
    res = await service.get_time_slot(id, current_user.school_id)
    return SuccessResponse[TimeSlotResponse](data=res)


@router.put(
    "/time-slots/{id}",
    response_model=SuccessResponse[TimeSlotResponse],
    status_code=status.HTTP_200_OK,
)
async def update_time_slot(
    id: uuid.UUID,
    data: TimeSlotUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TimeSlotResponse]:
    require_permission(current_user, "timeslot.update")
    service = TimeSlotService(db)
    res = await service.update_time_slot(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[TimeSlotResponse](data=res)


@router.delete(
    "/time-slots/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_time_slot(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "timeslot.delete")
    service = TimeSlotService(db)
    await service.delete_time_slot(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Time slot deleted successfully.")


# ===========================================================================
# PERIODS ENDPOINTS
# ===========================================================================


@router.post(
    "/periods",
    response_model=CreatedResponse[PeriodResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_period(
    data: PeriodCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[PeriodResponse]:
    require_permission(current_user, "timeslot.create")
    service = TimeSlotService(db)
    res = await service.create_period(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[PeriodResponse](data=res)


@router.get(
    "/periods",
    response_model=SuccessResponse[list[PeriodResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_periods(
    time_slot_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[PeriodResponse]]:
    require_permission(current_user, "timeslot.read")
    service = TimeSlotService(db)
    res = await service.list_periods(
        school_id=current_user.school_id,
        time_slot_id=time_slot_id,
        class_id=class_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[PeriodResponse]](data=list(res))


@router.get(
    "/periods/{id}",
    response_model=SuccessResponse[PeriodResponse],
    status_code=status.HTTP_200_OK,
)
async def get_period(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[PeriodResponse]:
    require_permission(current_user, "timeslot.read")
    service = TimeSlotService(db)
    res = await service.get_period(id, current_user.school_id)
    return SuccessResponse[PeriodResponse](data=res)


@router.put(
    "/periods/{id}",
    response_model=SuccessResponse[PeriodResponse],
    status_code=status.HTTP_200_OK,
)
async def update_period(
    id: uuid.UUID,
    data: PeriodUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[PeriodResponse]:
    require_permission(current_user, "timeslot.update")
    service = TimeSlotService(db)
    res = await service.update_period(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[PeriodResponse](data=res)


@router.delete(
    "/periods/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_period(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "timeslot.delete")
    service = TimeSlotService(db)
    await service.delete_period(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Period deleted successfully.")


# ===========================================================================
# BREAK PERIODS ENDPOINTS
# ===========================================================================


@router.post(
    "/break-periods",
    response_model=CreatedResponse[BreakPeriodResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_break_period(
    data: BreakPeriodCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[BreakPeriodResponse]:
    require_permission(current_user, "timeslot.create")
    service = TimeSlotService(db)
    res = await service.create_break_period(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[BreakPeriodResponse](data=res)


@router.get(
    "/break-periods",
    response_model=SuccessResponse[list[BreakPeriodResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_break_periods(
    time_slot_id: uuid.UUID | None = Query(None),
    break_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[BreakPeriodResponse]]:
    require_permission(current_user, "timeslot.read")
    service = TimeSlotService(db)
    res = await service.list_break_periods(
        school_id=current_user.school_id,
        time_slot_id=time_slot_id,
        break_type=break_type,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[BreakPeriodResponse]](data=list(res))


@router.get(
    "/break-periods/{id}",
    response_model=SuccessResponse[BreakPeriodResponse],
    status_code=status.HTTP_200_OK,
)
async def get_break_period(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[BreakPeriodResponse]:
    require_permission(current_user, "timeslot.read")
    service = TimeSlotService(db)
    res = await service.get_break_period(id, current_user.school_id)
    return SuccessResponse[BreakPeriodResponse](data=res)


@router.put(
    "/break-periods/{id}",
    response_model=SuccessResponse[BreakPeriodResponse],
    status_code=status.HTTP_200_OK,
)
async def update_break_period(
    id: uuid.UUID,
    data: BreakPeriodUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[BreakPeriodResponse]:
    require_permission(current_user, "timeslot.update")
    service = TimeSlotService(db)
    res = await service.update_break_period(
        id, current_user.school_id, data, current_user
    )
    await db.commit()
    return SuccessResponse[BreakPeriodResponse](data=res)


@router.delete(
    "/break-periods/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_break_period(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "timeslot.delete")
    service = TimeSlotService(db)
    await service.delete_break_period(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Break period deleted successfully.")
