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
from app.modules.class_subject_mapping.enums import ClassSubjectStatus
from app.modules.class_subject_mapping.exceptions import (
    ClassSubjectMappingNotFoundException,
)
from app.modules.class_subject_mapping.schemas import (
    ClassSubjectCreate,
    ClassSubjectResponse,
    ClassSubjectUpdate,
)
from app.modules.class_subject_mapping.service import ClassSubjectService

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


def _make_service(db: AsyncSession) -> ClassSubjectService:
    return ClassSubjectService(db)


@router.post(
    "",
    response_model=CreatedResponse[ClassSubjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Class Subject Mapping",
    responses={
        201: {"description": "Mapping created successfully."},
        400: {"description": "Unique order constraint conflict, or bad values."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'class_subject.create' required."},
    },
)
async def create_mapping(
    body: ClassSubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.create")
    service = _make_service(db)
    mapping = await service.create_class_subject_mapping(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(mapping)

    return CreatedResponse[ClassSubjectResponse](
        message="Class Subject mapping created successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[ClassSubjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Class Subject Mappings",
)
async def list_mappings(
    academic_year_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Academic Year")
    ] = None,
    term_id: Annotated[uuid.UUID | None, Query(description="Filter by Term")] = None,
    class_id: Annotated[uuid.UUID | None, Query(description="Filter by Class")] = None,
    section_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Section")
    ] = None,
    subject_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Subject")
    ] = None,
    subject_group_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Subject Group")
    ] = None,
    is_compulsory: Annotated[
        bool | None, Query(description="Filter by compulsory flag")
    ] = None,
    is_elective: Annotated[
        bool | None, Query(description="Filter by elective flag")
    ] = None,
    status_filter: Annotated[
        ClassSubjectStatus | None, Query(alias="status", description="Filter by status")
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
) -> SuccessResponse[list[ClassSubjectResponse]]:
    require_permission(current_user, "class_subject.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        subject_group_id=subject_group_id,
        is_compulsory=is_compulsory,
        is_elective=is_elective,
        status=status_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[ClassSubjectResponse]](
        message="Class Subject mappings list retrieved successfully.",
        data=[ClassSubjectResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Class Subject Mapping by ID",
)
async def get_mapping_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.read")
    service = _make_service(db)
    mapping = await service.repo.get_by_id(id)
    if not mapping or mapping.school_id != current_user.school_id:
        raise ClassSubjectMappingNotFoundException()

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping retrieved successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Class Subject Mapping",
)
async def update_mapping(
    id: uuid.UUID,
    body: ClassSubjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.update")
    service = _make_service(db)
    mapping = await service.update_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(mapping)

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping updated successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Class Subject Mapping",
)
async def delete_mapping(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "class_subject.delete")
    service = _make_service(db)
    res = await service.delete_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Class Subject mapping soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Class Subject Mapping",
)
async def activate_mapping(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.activate")
    service = _make_service(db)
    mapping = await service.activate_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(mapping)

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping activated successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Class Subject Mapping",
)
async def deactivate_mapping(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.activate")
    service = _make_service(db)
    mapping = await service.deactivate_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(mapping)

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping deactivated successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Class Subject Mapping",
)
async def lock_mapping(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.lock")
    service = _make_service(db)
    mapping = await service.lock_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(mapping)

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping locked successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Class Subject Mapping",
)
async def unlock_mapping(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.lock")
    service = _make_service(db)
    mapping = await service.unlock_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(mapping)

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping unlocked successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[ClassSubjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Class Subject Mapping",
)
async def archive_mapping(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[ClassSubjectResponse]:
    require_permission(current_user, "class_subject.archive")
    service = _make_service(db)
    mapping = await service.archive_class_subject_mapping(
        mapping_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(mapping)

    return SuccessResponse[ClassSubjectResponse](
        message="Class Subject mapping archived successfully.",
        data=ClassSubjectResponse.model_validate(mapping),
    )


@router.get(
    "/class/{class_id}",
    response_model=SuccessResponse[list[ClassSubjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Mappings by Class ID",
)
async def get_by_class(
    class_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClassSubjectResponse]]:
    require_permission(current_user, "class_subject.read")
    service = _make_service(db)
    items = await service.get_by_class_cached(class_id, current_user.school_id)

    return SuccessResponse[list[ClassSubjectResponse]](
        message="Class mappings retrieved successfully.",
        data=[ClassSubjectResponse.model_validate(i) for i in items],
    )


@router.get(
    "/section/{section_id}",
    response_model=SuccessResponse[list[ClassSubjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Mappings by Section ID",
)
async def get_by_section(
    section_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClassSubjectResponse]]:
    require_permission(current_user, "class_subject.read")
    service = _make_service(db)
    items = await service.get_by_section_cached(section_id, current_user.school_id)

    return SuccessResponse[list[ClassSubjectResponse]](
        message="Section mappings retrieved successfully.",
        data=[ClassSubjectResponse.model_validate(i) for i in items],
    )


@router.get(
    "/term/{term_id}",
    response_model=SuccessResponse[list[ClassSubjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Mappings by Term ID",
)
async def get_by_term(
    term_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClassSubjectResponse]]:
    require_permission(current_user, "class_subject.read")
    service = _make_service(db)
    items = await service.repo.get_by_term(current_user.school_id, term_id)

    return SuccessResponse[list[ClassSubjectResponse]](
        message="Term mappings retrieved successfully.",
        data=[ClassSubjectResponse.model_validate(i) for i in items],
    )


@router.get(
    "/subject/{subject_id}",
    response_model=SuccessResponse[list[ClassSubjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Mappings by Subject ID",
)
async def get_by_subject(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[ClassSubjectResponse]]:
    require_permission(current_user, "class_subject.read")
    service = _make_service(db)
    items = await service.repo.get_by_subject(current_user.school_id, subject_id)

    return SuccessResponse[list[ClassSubjectResponse]](
        message="Subject mappings retrieved successfully.",
        data=[ClassSubjectResponse.model_validate(i) for i in items],
    )
