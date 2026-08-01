import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.room.enums import MaintenanceStatus
from app.modules.room.schemas import (
    BuildingCreate,
    BuildingResponse,
    BuildingUpdate,
    FloorCreate,
    FloorResponse,
    FloorUpdate,
    RoomAllocationRuleCreate,
    RoomAllocationRuleResponse,
    RoomAllocationRuleUpdate,
    RoomCreate,
    RoomFacilityCreate,
    RoomFacilityResponse,
    RoomFacilityUpdate,
    RoomResponse,
    RoomSummaryResponse,
    RoomUpdate,
)
from app.modules.room.service import RoomService

router = APIRouter(tags=["Room Management"])


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
# BUILDINGS ENDPOINTS
# ===========================================================================


@router.post(
    "/buildings",
    response_model=CreatedResponse[BuildingResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_building(
    data: BuildingCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[BuildingResponse]:
    require_permission(current_user, "room.create")
    service = RoomService(db)
    res = await service.create_building(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[BuildingResponse](data=res)


@router.get(
    "/buildings",
    response_model=SuccessResponse[list[BuildingResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_buildings(
    status: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[BuildingResponse]]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.list_buildings(
        school_id=current_user.school_id,
        status=status,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[BuildingResponse]](data=list(res))


@router.get(
    "/buildings/{id}",
    response_model=SuccessResponse[BuildingResponse],
    status_code=status.HTTP_200_OK,
)
async def get_building(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[BuildingResponse]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.get_building(id, current_user.school_id)
    return SuccessResponse[BuildingResponse](data=res)


@router.put(
    "/buildings/{id}",
    response_model=SuccessResponse[BuildingResponse],
    status_code=status.HTTP_200_OK,
)
async def update_building(
    id: uuid.UUID,
    data: BuildingUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[BuildingResponse]:
    require_permission(current_user, "room.update")
    service = RoomService(db)
    res = await service.update_building(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[BuildingResponse](data=res)


@router.delete(
    "/buildings/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_building(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "room.delete")
    service = RoomService(db)
    await service.delete_building(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Building deleted successfully.")


# ===========================================================================
# FLOORS ENDPOINTS
# ===========================================================================


@router.post(
    "/floors",
    response_model=CreatedResponse[FloorResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_floor(
    data: FloorCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[FloorResponse]:
    require_permission(current_user, "room.create")
    service = RoomService(db)
    res = await service.create_floor(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[FloorResponse](data=res)


@router.get(
    "/floors",
    response_model=SuccessResponse[list[FloorResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_floors(
    building_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[FloorResponse]]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.list_floors(
        school_id=current_user.school_id,
        building_id=building_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[FloorResponse]](data=list(res))


@router.get(
    "/floors/{id}",
    response_model=SuccessResponse[FloorResponse],
    status_code=status.HTTP_200_OK,
)
async def get_floor(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[FloorResponse]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.get_floor(id, current_user.school_id)
    return SuccessResponse[FloorResponse](data=res)


@router.put(
    "/floors/{id}",
    response_model=SuccessResponse[FloorResponse],
    status_code=status.HTTP_200_OK,
)
async def update_floor(
    id: uuid.UUID,
    data: FloorUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[FloorResponse]:
    require_permission(current_user, "room.update")
    service = RoomService(db)
    res = await service.update_floor(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[FloorResponse](data=res)


@router.delete(
    "/floors/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_floor(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "room.delete")
    service = RoomService(db)
    await service.delete_floor(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Floor deleted successfully.")


# ===========================================================================
# ROOMS ENDPOINTS
# ===========================================================================


@router.get(
    "/rooms/summary",
    response_model=SuccessResponse[RoomSummaryResponse],
    status_code=status.HTTP_200_OK,
)
async def get_room_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomSummaryResponse]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.generate_room_summary(current_user.school_id)
    return SuccessResponse[RoomSummaryResponse](data=res)


@router.post(
    "/rooms",
    response_model=CreatedResponse[RoomResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_room(
    data: RoomCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[RoomResponse]:
    require_permission(current_user, "room.create")
    service = RoomService(db)
    res = await service.create_room(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[RoomResponse](data=res)


@router.get(
    "/rooms",
    response_model=SuccessResponse[list[RoomResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_rooms(
    building_id: uuid.UUID | None = Query(None),
    floor_id: uuid.UUID | None = Query(None),
    room_type: str | None = Query(None),
    min_capacity: int | None = Query(None),
    is_bookable: bool | None = Query(None),
    maintenance_status: str | None = Query(None),
    smart_classroom: bool | None = Query(None),
    is_laboratory: bool | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("room_name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[RoomResponse]]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.list_rooms(
        school_id=current_user.school_id,
        building_id=building_id,
        floor_id=floor_id,
        room_type=room_type,
        min_capacity=min_capacity,
        is_bookable=is_bookable,
        maintenance_status=maintenance_status,
        smart_classroom=smart_classroom,
        is_laboratory=is_laboratory,
        is_active=is_active,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[RoomResponse]](data=list(res))


@router.get(
    "/rooms/{id}",
    response_model=SuccessResponse[RoomResponse],
    status_code=status.HTTP_200_OK,
)
async def get_room(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomResponse]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.get_room(id, current_user.school_id)
    return SuccessResponse[RoomResponse](data=res)


@router.put(
    "/rooms/{id}",
    response_model=SuccessResponse[RoomResponse],
    status_code=status.HTTP_200_OK,
)
async def update_room(
    id: uuid.UUID,
    data: RoomUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomResponse]:
    require_permission(current_user, "room.update")
    service = RoomService(db)
    res = await service.update_room(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[RoomResponse](data=res)


@router.delete(
    "/rooms/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_room(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "room.delete")
    service = RoomService(db)
    await service.delete_room(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Room deleted successfully.")


@router.put(
    "/rooms/{id}/maintenance",
    response_model=SuccessResponse[RoomResponse],
    status_code=status.HTTP_200_OK,
)
async def update_room_maintenance(
    id: uuid.UUID,
    maintenance_status: MaintenanceStatus,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomResponse]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    res = await service.change_maintenance_status(
        id, current_user.school_id, maintenance_status, current_user
    )
    await db.commit()
    return SuccessResponse[RoomResponse](data=res)


@router.get(
    "/rooms/{id}/availability",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
)
async def check_room_availability(
    id: uuid.UUID,
    occupants: int = Query(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[bool]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.check_room_availability(current_user.school_id, id, occupants)
    return SuccessResponse[bool](data=res)


# ===========================================================================
# FACILITIES ENDPOINTS
# ===========================================================================


@router.post(
    "/facilities",
    response_model=CreatedResponse[RoomFacilityResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_facility(
    data: RoomFacilityCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[RoomFacilityResponse]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    res = await service.create_facility(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[RoomFacilityResponse](data=res)


@router.get(
    "/facilities",
    response_model=SuccessResponse[list[RoomFacilityResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_facilities(
    room_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[RoomFacilityResponse]]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.list_facilities(
        school_id=current_user.school_id,
        room_id=room_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[RoomFacilityResponse]](data=list(res))


@router.get(
    "/facilities/{id}",
    response_model=SuccessResponse[RoomFacilityResponse],
    status_code=status.HTTP_200_OK,
)
async def get_facility(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomFacilityResponse]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.get_facility(id, current_user.school_id)
    return SuccessResponse[RoomFacilityResponse](data=res)


@router.put(
    "/facilities/{id}",
    response_model=SuccessResponse[RoomFacilityResponse],
    status_code=status.HTTP_200_OK,
)
async def update_facility(
    id: uuid.UUID,
    data: RoomFacilityUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomFacilityResponse]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    res = await service.update_facility(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[RoomFacilityResponse](data=res)


@router.delete(
    "/facilities/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_facility(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    await service.delete_facility(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Facility deleted successfully.")


# ===========================================================================
# ALLOCATION RULES ENDPOINTS
# ===========================================================================


@router.post(
    "/allocation-rules",
    response_model=CreatedResponse[RoomAllocationRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_allocation_rule(
    data: RoomAllocationRuleCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[RoomAllocationRuleResponse]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    res = await service.create_allocation_rule(
        current_user.school_id, data, current_user
    )
    await db.commit()
    return CreatedResponse[RoomAllocationRuleResponse](data=res)


@router.get(
    "/allocation-rules",
    response_model=SuccessResponse[list[RoomAllocationRuleResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_allocation_rules(
    room_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[RoomAllocationRuleResponse]]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.list_allocation_rules(
        school_id=current_user.school_id,
        room_id=room_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[RoomAllocationRuleResponse]](data=list(res))


@router.get(
    "/allocation-rules/{id}",
    response_model=SuccessResponse[RoomAllocationRuleResponse],
    status_code=status.HTTP_200_OK,
)
async def get_allocation_rule(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomAllocationRuleResponse]:
    require_permission(current_user, "room.read")
    service = RoomService(db)
    res = await service.get_allocation_rule(id, current_user.school_id)
    return SuccessResponse[RoomAllocationRuleResponse](data=res)


@router.put(
    "/allocation-rules/{id}",
    response_model=SuccessResponse[RoomAllocationRuleResponse],
    status_code=status.HTTP_200_OK,
)
async def update_allocation_rule(
    id: uuid.UUID,
    data: RoomAllocationRuleUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[RoomAllocationRuleResponse]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    res = await service.update_allocation_rule(
        id, current_user.school_id, data, current_user
    )
    await db.commit()
    return SuccessResponse[RoomAllocationRuleResponse](data=res)


@router.delete(
    "/allocation-rules/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_allocation_rule(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "room.manage")
    service = RoomService(db)
    await service.delete_allocation_rule(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Allocation rule deleted successfully.")
