import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.common.responses import (
    CreatedResponse,
    SuccessResponse,
)
from app.db.database import get_db
from app.models.user import User
from app.modules.section_management.enums import SectionStatus
from app.modules.section_management.exceptions import SectionNotFoundException
from app.modules.section_management.schemas import (
    SectionCreate,
    SectionResponse,
    SectionUpdate,
)
from app.modules.section_management.service import SectionService

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


def _make_service(db: AsyncSession) -> SectionService:
    return SectionService(db)


@router.post(
    "",
    response_model=CreatedResponse[SectionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Section",
    responses={
        201: {"description": "Section created successfully."},
        400: {"description": "Unique name/code/display_order conflict, or bad values."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'section.create' required."},
    },
)
async def create_section(
    body: SectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[SectionResponse]:
    require_permission(current_user, "section.create")
    service = _make_service(db)
    sec = await service.create_section(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(sec)

    return CreatedResponse[SectionResponse](
        message="Section created successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[SectionResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Sections",
)
async def list_sections(
    academic_year_id: Annotated[uuid.UUID | None, Query(description="Filter by Academic Year")] = None,
    class_id: Annotated[uuid.UUID | None, Query(description="Filter by Class")] = None,
    status_filter: Annotated[SectionStatus | None, Query(alias="status", description="Filter by status")] = None,
    name: Annotated[str | None, Query(description="Filter by name")] = None,
    code: Annotated[str | None, Query(description="Filter by code")] = None,
    capacity: Annotated[int | None, Query(description="Filter by capacity")] = None,
    sort_by: Annotated[str | None, Query(description="Sort field name")] = "display_order",
    sort_dir: Annotated[str | None, Query(description="Sort direction (asc/desc)")] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SectionResponse]]:
    require_permission(current_user, "section.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        class_id=class_id,
        status=status_filter,
        name=name,
        code=code,
        capacity=capacity,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[SectionResponse]](
        message="Sections list retrieved successfully.",
        data=[SectionResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/class/{class_id}",
    response_model=SuccessResponse[list[SectionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Sections by Class ID",
)
async def get_sections_by_class(
    class_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SectionResponse]]:
    require_permission(current_user, "section.read")
    service = _make_service(db)
    items = await service.get_by_class_cached(class_id)
    # Ensure multi-tenant security
    for item in items:
        if item.school_id != current_user.school_id:
            raise ForbiddenException("Access to this class's sections is restricted.")

    return SuccessResponse[list[SectionResponse]](
        message="Sections list for Class retrieved successfully.",
        data=[SectionResponse.model_validate(i) for i in items],
    )


@router.get(
    "/academic-year/{academic_year_id}",
    response_model=SuccessResponse[list[SectionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Sections by Academic Year ID",
)
async def get_sections_by_academic_year(
    academic_year_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SectionResponse]]:
    require_permission(current_user, "section.read")
    service = _make_service(db)
    items = await service.get_by_academic_year_cached(academic_year_id)
    # Ensure multi-tenant security
    for item in items:
        if item.school_id != current_user.school_id:
            raise ForbiddenException("Access to this academic year's sections is restricted.")

    return SuccessResponse[list[SectionResponse]](
        message="Sections list for Academic Year retrieved successfully.",
        data=[SectionResponse.model_validate(i) for i in items],
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Section by ID",
)
async def get_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.read")
    service = _make_service(db)
    sec = await service.repo.get_by_id(id)
    if not sec or sec.school_id != current_user.school_id:
        raise SectionNotFoundException()

    return SuccessResponse[SectionResponse](
        message="Section retrieved successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Section",
)
async def update_section(
    id: uuid.UUID,
    body: SectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.update")
    service = _make_service(db)
    sec = await service.update_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section updated successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Section",
)
async def delete_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "section.delete")
    service = _make_service(db)
    res = await service.delete_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Section soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Section",
)
async def activate_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.activate")
    service = _make_service(db)
    sec = await service.activate_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section activated successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Section",
)
async def deactivate_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.activate")
    service = _make_service(db)
    sec = await service.deactivate_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section deactivated successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.patch(
    "/{id}/default",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Set default Section within Class",
)
async def set_default_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.default")
    service = _make_service(db)
    sec = await service.set_default_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section set as default successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Section",
)
async def lock_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.lock")
    service = _make_service(db)
    sec = await service.lock_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section locked successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Section",
)
async def unlock_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.lock")
    service = _make_service(db)
    sec = await service.unlock_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section unlocked successfully.",
        data=SectionResponse.model_validate(sec),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[SectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Section",
)
async def archive_section(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SectionResponse]:
    require_permission(current_user, "section.archive")
    service = _make_service(db)
    sec = await service.archive_section(
        section_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sec)

    return SuccessResponse[SectionResponse](
        message="Section archived successfully.",
        data=SectionResponse.model_validate(sec),
    )
