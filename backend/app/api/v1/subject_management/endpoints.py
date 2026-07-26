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
from app.modules.subject_management.enums import SubjectStatus, SubjectType
from app.modules.subject_management.schemas import (
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
)
from app.modules.subject_management.service import SubjectService

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


def _make_service(db: AsyncSession) -> SubjectService:
    return SubjectService(db)


@router.post(
    "",
    response_model=CreatedResponse[SubjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Subject",
    responses={
        201: {"description": "Subject created successfully."},
        400: {"description": "Unique code/name conflict, or bad validation values."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'subject.create' required."},
    },
)
async def create_subject(
    body: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[SubjectResponse]:
    require_permission(current_user, "subject.create")
    service = _make_service(db)
    sub = await service.create_subject(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(sub)

    return CreatedResponse[SubjectResponse](
        message="Subject created successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[SubjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Subjects",
)
async def list_subjects(
    subject_type: Annotated[
        SubjectType | None, Query(description="Filter by type")
    ] = None,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    status_filter: Annotated[
        SubjectStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    language: Annotated[str | None, Query(description="Filter by language")] = None,
    is_core: Annotated[bool | None, Query(description="Filter by core flag")] = None,
    is_elective: Annotated[
        bool | None, Query(description="Filter by elective flag")
    ] = None,
    query: Annotated[
        str | None, Query(description="Search in name, code or display name")
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
) -> SuccessResponse[list[SubjectResponse]]:
    require_permission(current_user, "subject.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        subject_type=subject_type,
        category=category,
        status=status_filter,
        language=language,
        is_core=is_core,
        is_elective=is_elective,
        query=query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[SubjectResponse]](
        message="Subjects list retrieved successfully.",
        data=[SubjectResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Subject by ID",
)
async def get_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.read")
    service = _make_service(db)
    sub = await service.get_subject_cached(id, current_user.school_id)

    return SuccessResponse[SubjectResponse](
        message="Subject retrieved successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Subject",
)
async def update_subject(
    id: uuid.UUID,
    body: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.update")
    service = _make_service(db)
    sub = await service.update_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(sub)

    return SuccessResponse[SubjectResponse](
        message="Subject updated successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Subject",
)
async def delete_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "subject.delete")
    service = _make_service(db)
    res = await service.delete_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Subject soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Subject",
)
async def activate_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.activate")
    service = _make_service(db)
    sub = await service.activate_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sub)

    return SuccessResponse[SubjectResponse](
        message="Subject activated successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Subject",
)
async def deactivate_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.activate")
    service = _make_service(db)
    sub = await service.deactivate_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sub)

    return SuccessResponse[SubjectResponse](
        message="Subject deactivated successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Subject",
)
async def lock_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.lock")
    service = _make_service(db)
    sub = await service.lock_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sub)

    return SuccessResponse[SubjectResponse](
        message="Subject locked successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Subject",
)
async def unlock_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.lock")
    service = _make_service(db)
    sub = await service.unlock_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sub)

    return SuccessResponse[SubjectResponse](
        message="Subject unlocked successfully.",
        data=SubjectResponse.model_validate(sub),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[SubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Subject",
)
async def archive_subject(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[SubjectResponse]:
    require_permission(current_user, "subject.archive")
    service = _make_service(db)
    sub = await service.archive_subject(
        subject_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(sub)

    return SuccessResponse[SubjectResponse](
        message="Subject archived successfully.",
        data=SubjectResponse.model_validate(sub),
    )
