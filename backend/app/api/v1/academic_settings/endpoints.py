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
from app.modules.academic_settings.enums import AcademicSettingsStatus
from app.modules.academic_settings.exceptions import AcademicSettingsNotFoundException
from app.modules.academic_settings.schemas import (
    AcademicSettingsCreate,
    AcademicSettingsResponse,
    AcademicSettingsUpdate,
)
from app.modules.academic_settings.service import AcademicSettingsService

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


def _make_service(db: AsyncSession) -> AcademicSettingsService:
    return AcademicSettingsService(db)


@router.post(
    "",
    response_model=CreatedResponse[AcademicSettingsResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Academic Settings",
)
async def create_settings(
    body: AcademicSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.create")
    service = _make_service(db)
    settings = await service.create_settings(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(settings)

    return CreatedResponse[AcademicSettingsResponse](
        message="Academic settings created successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[AcademicSettingsResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Academic Settings History",
)
async def list_settings(
    academic_year_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Academic Year")
    ] = None,
    status_filter: Annotated[
        AcademicSettingsStatus | None,
        Query(alias="status", description="Filter by status"),
    ] = None,
    sort_by: Annotated[str | None, Query(description="Sort field name")] = "created_at",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "desc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AcademicSettingsResponse]]:
    require_permission(current_user, "academic_settings.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        status=status_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[AcademicSettingsResponse]](
        message="Academic settings history list retrieved successfully.",
        data=[AcademicSettingsResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/active",
    response_model=SuccessResponse[AcademicSettingsResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get Active Academic Settings",
)
async def get_active_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse | None]:
    require_permission(current_user, "academic_settings.read")
    service = _make_service(db)
    settings = await service.get_active_cached(current_user.school_id)

    return SuccessResponse[AcademicSettingsResponse | None](
        message="Active academic settings retrieved successfully.",
        data=AcademicSettingsResponse.model_validate(settings) if settings else None,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Academic Settings by ID",
)
async def get_settings_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.read")
    service = _make_service(db)
    settings = await service.repo.get_by_id(id)
    if not settings or settings.school_id != current_user.school_id:
        raise AcademicSettingsNotFoundException()

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings retrieved successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Academic Settings",
)
async def update_settings(
    id: uuid.UUID,
    body: AcademicSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.update")
    service = _make_service(db)
    settings = await service.update_settings(
        settings_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(settings)

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings updated successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Academic Settings",
)
async def activate_settings(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.activate")
    service = _make_service(db)
    settings = await service.activate_settings(
        settings_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(settings)

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings activated successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Academic Settings",
)
async def deactivate_settings(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.activate")
    service = _make_service(db)
    settings = await service.deactivate_settings(
        settings_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(settings)

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings deactivated successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Academic Settings",
)
async def lock_settings(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.lock")
    service = _make_service(db)
    settings = await service.lock_settings(
        settings_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(settings)

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings locked successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Academic Settings",
)
async def unlock_settings(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.lock")
    service = _make_service(db)
    settings = await service.unlock_settings(
        settings_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(settings)

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings unlocked successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[AcademicSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Academic Settings",
)
async def archive_settings(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AcademicSettingsResponse]:
    require_permission(current_user, "academic_settings.archive")
    service = _make_service(db)
    settings = await service.archive_settings(
        settings_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(settings)

    return SuccessResponse[AcademicSettingsResponse](
        message="Academic settings archived successfully.",
        data=AcademicSettingsResponse.model_validate(settings),
    )
