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
from app.modules.department.enums import DepartmentStatus
from app.modules.department.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.modules.department.service import DepartmentService

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


def _make_service(db: AsyncSession) -> DepartmentService:
    return DepartmentService(db)


@router.post(
    "",
    response_model=CreatedResponse[DepartmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Department",
)
async def create_department(
    body: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[DepartmentResponse]:
    require_permission(current_user, "department.create")
    service = _make_service(db)
    dept = await service.create_department(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(dept)

    return CreatedResponse[DepartmentResponse](
        message="Department created successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[DepartmentResponse]],
    status_code=status.HTTP_200_OK,
    summary="List/Search Departments",
)
async def list_departments(
    name: Annotated[str | None, Query(description="Filter by department name")] = None,
    code: Annotated[str | None, Query(description="Filter by department code")] = None,
    is_academic: Annotated[
        bool | None, Query(description="Filter by academic flag")
    ] = None,
    status_filter: Annotated[
        DepartmentStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    location: Annotated[str | None, Query(description="Filter by location")] = None,
    building: Annotated[
        str | None, Query(description="Filter by building name")
    ] = None,
    sort_by: Annotated[
        str | None, Query(description="Sort field name")
    ] = "department_name",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[DepartmentResponse]]:
    require_permission(current_user, "department.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        name=name,
        code=code,
        is_academic=is_academic,
        status=status_filter,
        location=location,
        building=building,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[DepartmentResponse]](
        message="Departments list retrieved successfully.",
        data=[DepartmentResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Department by ID",
)
async def get_department_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.read")
    service = _make_service(db)
    dept = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[DepartmentResponse](
        message="Department details retrieved successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Department",
)
async def update_department(
    id: uuid.UUID,
    body: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.update")
    service = _make_service(db)
    dept = await service.update_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department updated successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Department",
)
async def delete_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.delete")
    service = _make_service(db)
    dept = await service.delete_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department soft-deleted successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Department",
)
async def restore_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.delete")
    service = _make_service(db)
    dept = await service.restore_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department restored successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Department",
)
async def activate_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.activate")
    service = _make_service(db)
    dept = await service.activate_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department activated successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Department",
)
async def deactivate_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.activate")
    service = _make_service(db)
    dept = await service.deactivate_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department deactivated successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Department",
)
async def lock_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.lock")
    service = _make_service(db)
    dept = await service.lock_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department locked successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Department",
)
async def unlock_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.lock")
    service = _make_service(db)
    dept = await service.unlock_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department unlocked successfully.",
        data=DepartmentResponse.model_validate(dept),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Department",
)
async def archive_department(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[DepartmentResponse]:
    require_permission(current_user, "department.archive")
    service = _make_service(db)
    dept = await service.archive_department(
        dept_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(dept)

    return SuccessResponse[DepartmentResponse](
        message="Department archived successfully.",
        data=DepartmentResponse.model_validate(dept),
    )
