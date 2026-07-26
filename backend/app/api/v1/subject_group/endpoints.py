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
from app.modules.subject_group.enums import SubjectGroupStatus
from app.modules.subject_group.exceptions import SubjectGroupNotFoundException
from app.modules.subject_group.schemas import (
    SubjectGroupCreate,
    SubjectGroupResponse,
    SubjectGroupUpdate,
    SubjectMappingCreate,
    SubjectMappingResponse,
)
from app.modules.subject_group.service import SubjectGroupService

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


def _make_service(db: AsyncSession) -> SubjectGroupService:
    return SubjectGroupService(db)


@router.post(
    "",
    response_model=CreatedResponse[SubjectGroupResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Subject Group",
    responses={
        201: {"description": "Subject Group created successfully."},
        400: {"description": "Unique code/name conflict, or bad values."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'subject_group.create' required."},
    },
)
async def create_subject_group(
    body: SubjectGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.create")
    service = _make_service(db)
    group = await service.create_subject_group(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(group)

    return CreatedResponse[SubjectGroupResponse](
        message="Subject Group created successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[SubjectGroupResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Subject Groups",
)
async def list_subject_groups(
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    status_filter: Annotated[
        SubjectGroupStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    is_core: Annotated[bool | None, Query(description="Filter by core flag")] = None,
    is_elective: Annotated[
        bool | None, Query(description="Filter by elective flag")
    ] = None,
    query: Annotated[str | None, Query(description="Search in name or code")] = None,
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
) -> SuccessResponse[list[SubjectGroupResponse]]:
    require_permission(current_user, "subject_group.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        category=category,
        status=status_filter,
        is_core=is_core,
        is_elective=is_elective,
        query=query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[SubjectGroupResponse]](
        message="Subject Groups list retrieved successfully.",
        data=[SubjectGroupResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Subject Group by ID",
)
async def get_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.read")
    service = _make_service(db)
    group = await service.repo.get_by_id(id)
    if not group or group.school_id != current_user.school_id:
        raise SubjectGroupNotFoundException()

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group retrieved successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Subject Group",
)
async def update_subject_group(
    id: uuid.UUID,
    body: SubjectGroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.update")
    service = _make_service(db)
    group = await service.update_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(group)

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group updated successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Subject Group",
)
async def delete_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "subject_group.delete")
    service = _make_service(db)
    res = await service.delete_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Subject Group soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Subject Group",
)
async def activate_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.activate")
    service = _make_service(db)
    group = await service.activate_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(group)

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group activated successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Subject Group",
)
async def deactivate_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.activate")
    service = _make_service(db)
    group = await service.deactivate_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(group)

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group deactivated successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Subject Group",
)
async def lock_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.lock")
    service = _make_service(db)
    group = await service.lock_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(group)

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group locked successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Subject Group",
)
async def unlock_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.lock")
    service = _make_service(db)
    group = await service.unlock_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(group)

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group unlocked successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[SubjectGroupResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Subject Group",
)
async def archive_subject_group(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectGroupResponse]:
    require_permission(current_user, "subject_group.archive")
    service = _make_service(db)
    group = await service.archive_subject_group(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(group)

    return SuccessResponse[SubjectGroupResponse](
        message="Subject Group archived successfully.",
        data=SubjectGroupResponse.model_validate(group),
    )


# ==========================
# Subject Mapping Endpoints
# ==========================


@router.post(
    "/{id}/subjects",
    response_model=CreatedResponse[SubjectMappingResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add Subject Mapping to Group",
)
async def add_subject_mapping(
    id: uuid.UUID,
    body: SubjectMappingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[SubjectMappingResponse]:
    require_permission(current_user, "subject_group.manage_subjects")
    service = _make_service(db)
    mapping = await service.add_subject_mapping(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        subject_id=body.subject_id,
        display_order=body.display_order,
        is_mandatory=body.is_mandatory,
    )
    await db.commit()
    await db.refresh(mapping)

    return CreatedResponse[SubjectMappingResponse](
        message="Subject mapped to group successfully.",
        data=SubjectMappingResponse.model_validate(mapping),
    )


@router.delete(
    "/{id}/subjects/{subject_id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Remove Subject Mapping from Group",
)
async def remove_subject_mapping(
    id: uuid.UUID,
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "subject_group.manage_subjects")
    service = _make_service(db)
    res = await service.remove_subject_mapping(
        group_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        subject_id=subject_id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Subject mapping removed successfully.",
        data=res,
    )


@router.get(
    "/{id}/subjects",
    response_model=SuccessResponse[list[SubjectMappingResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Subjects Mapped to Group",
)
async def list_group_subjects(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[SubjectMappingResponse]]:
    require_permission(current_user, "subject_group.read")
    service = _make_service(db)
    items = await service.list_subjects_cached(id, current_user.school_id)

    return SuccessResponse[list[SubjectMappingResponse]](
        message="Mapped subjects list retrieved successfully.",
        data=[SubjectMappingResponse.model_validate(i) for i in items],
    )
