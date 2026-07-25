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
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.exceptions import AcademicYearNotFoundException
from app.modules.academic_year.schemas import (
    AcademicYearCreate,
    AcademicYearResponse,
    AcademicYearUpdate,
)
from app.modules.academic_year.service import AcademicYearService

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


def _make_service(db: AsyncSession) -> AcademicYearService:
    return AcademicYearService(db)


@router.post(
    "",
    response_model=CreatedResponse[AcademicYearResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Academic Year",
    responses={
        201: {"description": "Academic Year created successfully."},
        400: {"description": "Date range overlap, or unique code/name conflict."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'academic_year.create' required."},
    },
)
async def create_academic_year(
    body: AcademicYearCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.create")
    service = _make_service(db)
    ay = await service.create_academic_year(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(ay)

    return CreatedResponse[AcademicYearResponse](
        message="Academic Year created successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[AcademicYearResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Academic Years",
)
async def list_academic_years(
    name: Annotated[str | None, Query(description="Filter by name")] = None,
    code: Annotated[str | None, Query(description="Filter by code")] = None,
    status_filter: Annotated[
        AcademicYearStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    search: Annotated[str | None, Query(description="General search name/code")] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AcademicYearResponse]]:
    require_permission(current_user, "academic_year.read")
    service = _make_service(db)
    items = await service.repo.list_all(
        school_id=current_user.school_id,
        name=name,
        code=code,
        status=status_filter,
        search=search,
    )
    return SuccessResponse[list[AcademicYearResponse]](
        message="Academic Years list retrieved successfully.",
        data=[AcademicYearResponse.model_validate(i) for i in items],
    )


@router.get(
    "/active",
    response_model=SuccessResponse[AcademicYearResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get active Academic Year",
)
async def get_active_year(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse | None]:
    require_permission(current_user, "academic_year.read")
    service = _make_service(db)
    ay = await service.get_active_cached(current_user.school_id)
    return SuccessResponse[AcademicYearResponse | None](
        message="Active Academic Year resolved successfully.",
        data=AcademicYearResponse.model_validate(ay) if ay else None,
    )


@router.get(
    "/default",
    response_model=SuccessResponse[AcademicYearResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get default Academic Year",
)
async def get_default_year(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse | None]:
    require_permission(current_user, "academic_year.read")
    service = _make_service(db)
    ay = await service.get_default_cached(current_user.school_id)
    return SuccessResponse[AcademicYearResponse | None](
        message="Default Academic Year resolved successfully.",
        data=AcademicYearResponse.model_validate(ay) if ay else None,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Academic Year by ID",
)
async def get_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.read")
    service = _make_service(db)
    ay = await service.repo.get_by_id(id)
    if not ay or ay.school_id != current_user.school_id:
        raise AcademicYearNotFoundException()

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year retrieved successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Academic Year",
)
async def update_academic_year(
    id: uuid.UUID,
    body: AcademicYearUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.update")
    service = _make_service(db)
    ay = await service.update_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year updated successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Academic Year",
)
async def delete_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "academic_year.delete")
    service = _make_service(db)
    res = await service.delete_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Academic Year soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Academic Year",
)
async def activate_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.activate")
    service = _make_service(db)
    ay = await service.activate_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year activated successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Academic Year",
)
async def deactivate_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.activate")
    service = _make_service(db)
    ay = await service.deactivate_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year deactivated successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.patch(
    "/{id}/default",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Set default Academic Year",
)
async def set_default_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.default")
    service = _make_service(db)
    ay = await service.set_default_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year set as default successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Academic Year",
)
async def lock_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.lock")
    service = _make_service(db)
    ay = await service.lock_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year locked successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Academic Year",
)
async def unlock_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.lock")
    service = _make_service(db)
    ay = await service.unlock_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year unlocked successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[AcademicYearResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Academic Year",
)
async def archive_academic_year(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicYearResponse]:
    require_permission(current_user, "academic_year.archive")
    service = _make_service(db)
    ay = await service.archive_academic_year(
        ay_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(ay)

    return SuccessResponse[AcademicYearResponse](
        message="Academic Year archived successfully.",
        data=AcademicYearResponse.model_validate(ay),
    )
