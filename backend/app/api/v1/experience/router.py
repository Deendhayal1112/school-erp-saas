import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.experience.enums import EmploymentType, ExperienceStatus
from app.modules.experience.schemas import (
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
)
from app.modules.experience.service import ExperienceService

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


def _make_service(db: AsyncSession) -> ExperienceService:
    return ExperienceService(db)


@router.post(
    "",
    response_model=CreatedResponse[ExperienceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Experience Record",
)
async def create_experience(
    body: ExperienceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[ExperienceResponse]:
    require_permission(current_user, "experience.create")
    service = _make_service(db)
    exp = await service.create_experience(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(exp)

    return CreatedResponse[ExperienceResponse](
        message="Experience record created successfully.",
        data=service.map_to_response(exp),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[ExperienceResponse]],
    status_code=status.HTTP_200_OK,
    summary="List/Search Experience Records",
)
async def list_experiences(
    employee_id: Annotated[
        uuid.UUID | None, Query(description="Filter by employee ID")
    ] = None,
    employment_type: Annotated[
        EmploymentType | None, Query(description="Filter by employment type")
    ] = None,
    organization_name: Annotated[
        str | None, Query(description="Filter by organization name (partial match)")
    ] = None,
    is_verified: Annotated[
        bool | None, Query(description="Filter by verification flag")
    ] = None,
    currently_working: Annotated[
        bool | None, Query(description="Filter by currently working flag")
    ] = None,
    status: Annotated[
        ExperienceStatus | None, Query(description="Filter by status")
    ] = None,
    query: Annotated[
        str | None,
        Query(description="General query to search by name/designation/department"),
    ] = None,
    sort_by: Annotated[str | None, Query(description="Sort field name")] = "start_date",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "desc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ExperienceResponse]]:
    require_permission(current_user, "experience.read")
    service = _make_service(db)
    offset = (page - 1) * limit

    if query:
        items, total = await service.repo.search(
            school_id=current_user.school_id,
            query=query,
            limit=limit,
            offset=offset,
        )
    else:
        items, total = await service.repo.list(
            school_id=current_user.school_id,
            employee_id=employee_id,
            employment_type=employment_type,
            organization_name=organization_name,
            is_verified=is_verified,
            currently_working=currently_working,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    return SuccessResponse[list[ExperienceResponse]](
        message="Experience list retrieved successfully.",
        data=[service.map_to_response(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/employee/{employee_id}",
    response_model=SuccessResponse[list[ExperienceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Experience Records by Employee ID",
)
async def get_experiences_by_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ExperienceResponse]]:
    require_permission(current_user, "experience.read")
    service = _make_service(db)
    items = await service.get_by_employee_cached(employee_id, current_user.school_id)

    return SuccessResponse[list[ExperienceResponse]](
        message="Employee experience records retrieved successfully.",
        data=items,
    )


@router.get(
    "/employee/{employee_id}/total",
    response_model=SuccessResponse[dict[str, int]],
    status_code=status.HTTP_200_OK,
    summary="Calculate Total Verified Experience of Employee",
)
async def get_total_experience(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[dict[str, int]]:
    require_permission(current_user, "experience.read")
    service = _make_service(db)
    totals = await service.calculate_total_experience(
        employee_id, current_user.school_id
    )

    return SuccessResponse[dict[str, int]](
        message="Total employee experience calculated successfully.",
        data=totals,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Experience Record by ID",
)
async def get_experience_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.read")
    service = _make_service(db)
    resp = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[ExperienceResponse](
        message="Experience record details retrieved successfully.",
        data=resp,
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Experience Details",
)
async def update_experience(
    id: uuid.UUID,
    body: ExperienceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.update")
    service = _make_service(db)
    exp = await service.update_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience record details updated successfully.",
        data=service.map_to_response(exp),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Experience Record",
)
async def delete_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.delete")
    service = _make_service(db)
    exp = await service.delete_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience record soft-deleted successfully.",
        data=service.map_to_response(exp),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Experience Record",
)
async def restore_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.delete")
    service = _make_service(db)
    exp = await service.restore_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience record restored successfully.",
        data=service.map_to_response(exp),
    )


@router.patch(
    "/{id}/verify",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify Experience Record",
)
async def verify_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.verify")
    service = _make_service(db)
    exp = await service.verify_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience record verified successfully.",
        data=service.map_to_response(exp),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Experience",
)
async def activate_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.activate")
    service = _make_service(db)
    exp = await service.activate_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience activated successfully.",
        data=service.map_to_response(exp),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Experience",
)
async def deactivate_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.activate")
    service = _make_service(db)
    exp = await service.deactivate_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience deactivated successfully.",
        data=service.map_to_response(exp),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Experience",
)
async def lock_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.activate")
    service = _make_service(db)
    exp = await service.lock_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience locked successfully.",
        data=service.map_to_response(exp),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Experience",
)
async def unlock_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.activate")
    service = _make_service(db)
    exp = await service.unlock_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience unlocked successfully.",
        data=service.map_to_response(exp),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[ExperienceResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Experience",
)
async def archive_experience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ExperienceResponse]:
    require_permission(current_user, "experience.archive")
    service = _make_service(db)
    exp = await service.archive_experience(
        exp_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(exp)

    return SuccessResponse[ExperienceResponse](
        message="Experience archived successfully.",
        data=service.map_to_response(exp),
    )
