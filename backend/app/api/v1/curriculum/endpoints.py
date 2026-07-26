import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import (
    CreatedResponse,
    SuccessResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.curriculum.enums import CurriculumStatus
from app.modules.curriculum.exceptions import CurriculumNotFoundException
from app.modules.curriculum.schemas import (
    CurriculumCreate,
    CurriculumResponse,
    CurriculumUnitCreate,
    CurriculumUnitResponse,
    CurriculumUnitUpdate,
    CurriculumUpdate,
)
from app.modules.curriculum.service import CurriculumService

router = APIRouter()


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


def _make_service(db: AsyncSession) -> CurriculumService:
    return CurriculumService(db)


@router.post(
    "",
    response_model=CreatedResponse[CurriculumResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Curriculum",
)
async def create_curriculum(
    body: CurriculumCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.create")
    service = _make_service(db)
    curr = await service.create_curriculum(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(curr)

    return CreatedResponse[CurriculumResponse](
        message="Curriculum created successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[CurriculumResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Curriculums",
)
async def list_curriculums(
    academic_year_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Academic Year")
    ] = None,
    term_id: Annotated[uuid.UUID | None, Query(description="Filter by Term")] = None,
    class_id: Annotated[uuid.UUID | None, Query(description="Filter by Class")] = None,
    subject_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Subject")
    ] = None,
    status_filter: Annotated[
        CurriculumStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    completion_min: Annotated[
        float | None, Query(description="Filter by minimum completion percentage")
    ] = None,
    estimated_hours_max: Annotated[
        int | None, Query(description="Filter by maximum estimated hours")
    ] = None,
    sort_by: Annotated[
        str | None, Query(description="Sort field name")
    ] = "display_order",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[CurriculumResponse]]:
    require_permission(current_user, "curriculum.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        subject_id=subject_id,
        status=status_filter,
        completion_min=completion_min,
        estimated_hours_max=estimated_hours_max,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[CurriculumResponse]](
        message="Curriculums list retrieved successfully.",
        data=[CurriculumResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Curriculum by ID",
)
async def get_curriculum_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.read")
    service = _make_service(db)
    curr = await service.repo.get_by_id(id)
    if not curr or curr.school_id != current_user.school_id:
        raise CurriculumNotFoundException()

    return SuccessResponse[CurriculumResponse](
        message="Curriculum retrieved successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Curriculum",
)
async def update_curriculum(
    id: uuid.UUID,
    body: CurriculumUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.update")
    service = _make_service(db)
    curr = await service.update_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(curr)

    return SuccessResponse[CurriculumResponse](
        message="Curriculum updated successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Curriculum (Soft-Delete)",
)
async def delete_curriculum(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "curriculum.delete")
    service = _make_service(db)
    res = await service.delete_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Curriculum soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Curriculum",
)
async def activate_curriculum(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.activate")
    service = _make_service(db)
    curr = await service.activate_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(curr)

    return SuccessResponse[CurriculumResponse](
        message="Curriculum activated successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Curriculum",
)
async def deactivate_curriculum(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.activate")
    service = _make_service(db)
    curr = await service.deactivate_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(curr)

    return SuccessResponse[CurriculumResponse](
        message="Curriculum deactivated successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Curriculum",
)
async def lock_curriculum(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.lock")
    service = _make_service(db)
    curr = await service.lock_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(curr)

    return SuccessResponse[CurriculumResponse](
        message="Curriculum locked successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Curriculum",
)
async def unlock_curriculum(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.lock")
    service = _make_service(db)
    curr = await service.unlock_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(curr)

    return SuccessResponse[CurriculumResponse](
        message="Curriculum unlocked successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[CurriculumResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Curriculum",
)
async def archive_curriculum(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumResponse]:
    require_permission(current_user, "curriculum.archive")
    service = _make_service(db)
    curr = await service.archive_curriculum(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(curr)

    return SuccessResponse[CurriculumResponse](
        message="Curriculum archived successfully.",
        data=CurriculumResponse.model_validate(curr),
    )


# ==========================
# Curriculum Unit Operations
# ==========================


@router.post(
    "/{id}/units",
    response_model=CreatedResponse[CurriculumUnitResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add Curriculum Unit",
)
async def add_unit(
    id: uuid.UUID,
    body: CurriculumUnitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[CurriculumUnitResponse]:
    require_permission(current_user, "curriculum.unit.manage")
    service = _make_service(db)
    unit = await service.add_curriculum_unit(
        curriculum_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(unit)

    return CreatedResponse[CurriculumUnitResponse](
        message="Curriculum unit added successfully.",
        data=CurriculumUnitResponse.model_validate(unit),
    )


@router.put(
    "/{id}/units/{unit_id}",
    response_model=SuccessResponse[CurriculumUnitResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Curriculum Unit",
)
async def update_unit(
    id: uuid.UUID,
    unit_id: uuid.UUID,
    body: CurriculumUnitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[CurriculumUnitResponse]:
    require_permission(current_user, "curriculum.unit.manage")
    service = _make_service(db)
    unit = await service.update_curriculum_unit(
        curriculum_id=id,
        unit_id=unit_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(unit)

    return SuccessResponse[CurriculumUnitResponse](
        message="Curriculum unit updated successfully.",
        data=CurriculumUnitResponse.model_validate(unit),
    )


@router.delete(
    "/{id}/units/{unit_id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Curriculum Unit",
)
async def delete_unit(
    id: uuid.UUID,
    unit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "curriculum.unit.manage")
    service = _make_service(db)
    res = await service.delete_curriculum_unit(
        curriculum_id=id,
        unit_id=unit_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Curriculum unit deleted successfully.",
        data=res,
    )


@router.get(
    "/{id}/units",
    response_model=SuccessResponse[list[CurriculumUnitResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Curriculum Units",
)
async def list_units(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[CurriculumUnitResponse]]:
    require_permission(current_user, "curriculum.read")
    service = _make_service(db)
    units = await service.list_units_cached(id, current_user.school_id)

    return SuccessResponse[list[CurriculumUnitResponse]](
        message="Curriculum units list retrieved successfully.",
        data=[CurriculumUnitResponse.model_validate(u) for u in units],
    )
