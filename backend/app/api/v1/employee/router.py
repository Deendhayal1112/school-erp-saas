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
from app.modules.employee.enums import EmployeeType, EmploymentStatus
from app.modules.employee.schemas import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.modules.employee.service import EmployeeService

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


def _make_service(db: AsyncSession) -> EmployeeService:
    return EmployeeService(db)


@router.post(
    "",
    response_model=CreatedResponse[EmployeeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Employee",
)
async def create_employee(
    body: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[EmployeeResponse]:
    require_permission(current_user, "employee.create")
    service = _make_service(db)
    emp = await service.create_employee(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(emp)

    return CreatedResponse[EmployeeResponse](
        message="Employee profile created successfully.",
        data=service.map_to_response(emp),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[EmployeeResponse]],
    status_code=status.HTTP_200_OK,
    summary="List/Search Employees",
)
async def list_employees(
    department_id: Annotated[
        uuid.UUID | None, Query(description="Filter by department ID")
    ] = None,
    designation_id: Annotated[
        uuid.UUID | None, Query(description="Filter by designation ID")
    ] = None,
    employee_type: Annotated[
        EmployeeType | None, Query(description="Filter by employee type")
    ] = None,
    employment_status: Annotated[
        EmploymentStatus | None, Query(description="Filter by employment status")
    ] = None,
    gender: Annotated[str | None, Query(description="Filter by gender")] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active flag")
    ] = None,
    sort_by: Annotated[
        str | None, Query(description="Sort field name")
    ] = "employee_number",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[EmployeeResponse]]:
    require_permission(current_user, "employee.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        department_id=department_id,
        designation_id=designation_id,
        employee_type=employee_type,
        employment_status=employment_status,
        gender=gender,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[EmployeeResponse]](
        message="Employee list retrieved successfully.",
        data=[service.map_to_response(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/department/{department_id}",
    response_model=SuccessResponse[list[EmployeeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Employees by Department ID",
)
async def get_employees_by_department(
    department_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[EmployeeResponse]]:
    require_permission(current_user, "employee.read")
    service = _make_service(db)
    items = await service.get_by_department_cached(
        department_id, current_user.school_id
    )

    return SuccessResponse[list[EmployeeResponse]](
        message="Department employees retrieved successfully.",
        data=items,
    )


@router.get(
    "/designation/{designation_id}",
    response_model=SuccessResponse[list[EmployeeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Employees by Designation ID",
)
async def get_employees_by_designation(
    designation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[EmployeeResponse]]:
    require_permission(current_user, "employee.read")
    service = _make_service(db)
    items = await service.get_by_designation_cached(
        designation_id, current_user.school_id
    )

    return SuccessResponse[list[EmployeeResponse]](
        message="Designation employees retrieved successfully.",
        data=items,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Employee by ID",
)
async def get_employee_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.read")
    service = _make_service(db)
    resp = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[EmployeeResponse](
        message="Employee details retrieved successfully.",
        data=resp,
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Employee",
)
async def update_employee(
    id: uuid.UUID,
    body: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.update")
    service = _make_service(db)
    emp = await service.update_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile updated successfully.",
        data=service.map_to_response(emp),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Employee",
)
async def delete_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.delete")
    service = _make_service(db)
    emp = await service.delete_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile soft-deleted successfully.",
        data=service.map_to_response(emp),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Employee",
)
async def restore_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.delete")
    service = _make_service(db)
    emp = await service.restore_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile restored successfully.",
        data=service.map_to_response(emp),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Employee",
)
async def activate_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.activate")
    service = _make_service(db)
    emp = await service.activate_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile activated successfully.",
        data=service.map_to_response(emp),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Employee",
)
async def deactivate_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.activate")
    service = _make_service(db)
    emp = await service.deactivate_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile deactivated successfully.",
        data=service.map_to_response(emp),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Employee",
)
async def lock_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.lock")
    service = _make_service(db)
    emp = await service.lock_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile locked successfully.",
        data=service.map_to_response(emp),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Employee",
)
async def unlock_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.lock")
    service = _make_service(db)
    emp = await service.unlock_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile unlocked successfully.",
        data=service.map_to_response(emp),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Employee",
)
async def archive_employee(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[EmployeeResponse]:
    require_permission(current_user, "employee.archive")
    service = _make_service(db)
    emp = await service.archive_employee(
        emp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(emp)

    return SuccessResponse[EmployeeResponse](
        message="Employee profile archived successfully.",
        data=service.map_to_response(emp),
    )
