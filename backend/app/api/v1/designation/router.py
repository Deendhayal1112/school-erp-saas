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
from app.modules.designation.enums import DesignationStatus
from app.modules.designation.schemas import (
    DesignationCreate,
    DesignationResponse,
    DesignationUpdate,
)
from app.modules.designation.service import DesignationService

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


def _make_service(db: AsyncSession) -> DesignationService:
    return DesignationService(db)


@router.post(
    "",
    response_model=CreatedResponse[DesignationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Designation",
)
async def create_designation(
    body: DesignationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[DesignationResponse]:
    require_permission(current_user, "designation.create")
    service = _make_service(db)
    des = await service.create_designation(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(des)

    return CreatedResponse[DesignationResponse](
        message="Designation created successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[DesignationResponse]],
    status_code=status.HTTP_200_OK,
    summary="List/Search Designations",
)
async def list_designations(
    department_id: Annotated[
        uuid.UUID | None, Query(description="Filter by department ID")
    ] = None,
    is_teaching: Annotated[
        bool | None, Query(description="Filter by teaching flag")
    ] = None,
    is_management: Annotated[
        bool | None, Query(description="Filter by management flag")
    ] = None,
    employment_category: Annotated[
        str | None, Query(description="Filter by employment category")
    ] = None,
    status_filter: Annotated[
        DesignationStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    job_level: Annotated[str | None, Query(description="Filter by job level")] = None,
    grade: Annotated[str | None, Query(description="Filter by grade")] = None,
    sort_by: Annotated[
        str | None, Query(description="Sort field name")
    ] = "designation_name",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[DesignationResponse]]:
    require_permission(current_user, "designation.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        department_id=department_id,
        is_teaching=is_teaching,
        is_management=is_management,
        employment_category=employment_category,
        status=status_filter,
        job_level=job_level,
        grade=grade,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[DesignationResponse]](
        message="Designations list retrieved successfully.",
        data=[DesignationResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/department/{department_id}",
    response_model=SuccessResponse[list[DesignationResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Designations by Department ID",
)
async def get_designations_by_department(
    department_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[DesignationResponse]]:
    require_permission(current_user, "designation.read")
    service = _make_service(db)
    items = await service.get_by_department_cached(
        department_id, current_user.school_id
    )

    return SuccessResponse[list[DesignationResponse]](
        message="Department designations retrieved successfully.",
        data=[DesignationResponse.model_validate(i) for i in items],
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Designation by ID",
)
async def get_designation_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.read")
    service = _make_service(db)
    des = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[DesignationResponse](
        message="Designation details retrieved successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Designation",
)
async def update_designation(
    id: uuid.UUID,
    body: DesignationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.update")
    service = _make_service(db)
    des = await service.update_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation updated successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Designation",
)
async def delete_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.delete")
    service = _make_service(db)
    des = await service.delete_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation soft-deleted successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Designation",
)
async def restore_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.delete")
    service = _make_service(db)
    des = await service.restore_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation restored successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Designation",
)
async def activate_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.activate")
    service = _make_service(db)
    des = await service.activate_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation activated successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Designation",
)
async def deactivate_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.activate")
    service = _make_service(db)
    des = await service.deactivate_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation deactivated successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Designation",
)
async def lock_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.lock")
    service = _make_service(db)
    des = await service.lock_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation locked successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Designation",
)
async def unlock_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.lock")
    service = _make_service(db)
    des = await service.unlock_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation unlocked successfully.",
        data=DesignationResponse.model_validate(des),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[DesignationResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Designation",
)
async def archive_designation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DesignationResponse]:
    require_permission(current_user, "designation.archive")
    service = _make_service(db)
    des = await service.archive_designation(
        des_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(des)

    return SuccessResponse[DesignationResponse](
        message="Designation archived successfully.",
        data=DesignationResponse.model_validate(des),
    )
