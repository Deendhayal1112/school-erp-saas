import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.teacher.enums import TeacherType
from app.modules.teacher.schemas import TeacherCreate, TeacherResponse, TeacherUpdate
from app.modules.teacher.service import TeacherService

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


def _make_service(db: AsyncSession) -> TeacherService:
    return TeacherService(db)


@router.post(
    "",
    response_model=CreatedResponse[TeacherResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Teacher Profile",
)
async def create_teacher(
    body: TeacherCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[TeacherResponse]:
    require_permission(current_user, "teacher.create")
    service = _make_service(db)
    teacher = await service.create_teacher_profile(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(teacher)

    return CreatedResponse[TeacherResponse](
        message="Teacher profile created successfully.",
        data=service.map_to_response(teacher),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[TeacherResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Teachers",
)
async def list_teachers(
    department_id: Annotated[
        uuid.UUID | None, Query(description="Filter by department ID")
    ] = None,
    joining_academic_year_id: Annotated[
        uuid.UUID | None, Query(description="Filter by joining academic year ID")
    ] = None,
    teacher_type: Annotated[
        TeacherType | None, Query(description="Filter by teacher type")
    ] = None,
    teaching_experience_years: Annotated[
        int | None, Query(description="Filter by exact years of experience")
    ] = None,
    is_class_teacher: Annotated[
        bool | None, Query(description="Filter by class teacher flag")
    ] = None,
    is_subject_teacher: Annotated[
        bool | None, Query(description="Filter by subject teacher flag")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active flag")
    ] = None,
    sort_by: Annotated[
        str | None, Query(description="Sort field name")
    ] = "teacher_code",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TeacherResponse]]:
    require_permission(current_user, "teacher.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list(
        school_id=current_user.school_id,
        department_id=department_id,
        joining_academic_year_id=joining_academic_year_id,
        teacher_type=teacher_type,
        teaching_experience_years=teaching_experience_years,
        is_class_teacher=is_class_teacher,
        is_subject_teacher=is_subject_teacher,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[TeacherResponse]](
        message="Teacher list retrieved successfully.",
        data=[service.map_to_response(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/search",
    response_model=SuccessResponse[list[TeacherResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search Teachers",
)
async def search_teachers(
    query: Annotated[
        str, Query(description="Search term (code, email, or employee name)")
    ],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TeacherResponse]]:
    require_permission(current_user, "teacher.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.search(
        school_id=current_user.school_id,
        query=query,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[TeacherResponse]](
        message="Teacher search completed successfully.",
        data=[service.map_to_response(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/employee/{employee_id}",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher by Employee ID",
)
async def get_teacher_by_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.read")
    service = _make_service(db)
    resp = await service.get_by_employee_cached(employee_id, current_user.school_id)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile details retrieved successfully.",
        data=resp,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Teacher by ID",
)
async def get_teacher_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.read")
    service = _make_service(db)
    resp = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile details retrieved successfully.",
        data=resp,
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Teacher Profile",
)
async def update_teacher(
    id: uuid.UUID,
    body: TeacherUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.update")
    service = _make_service(db)
    teacher = await service.update_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile updated successfully.",
        data=service.map_to_response(teacher),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Teacher Profile",
)
async def delete_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.delete")
    service = _make_service(db)
    teacher = await service.delete_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile soft-deleted successfully.",
        data=service.map_to_response(teacher),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Teacher Profile",
)
async def restore_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.delete")
    service = _make_service(db)
    teacher = await service.restore_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile restored successfully.",
        data=service.map_to_response(teacher),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Teacher Profile",
)
async def activate_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.activate")
    service = _make_service(db)
    teacher = await service.activate_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile activated successfully.",
        data=service.map_to_response(teacher),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Teacher Profile",
)
async def deactivate_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.activate")
    service = _make_service(db)
    teacher = await service.deactivate_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile deactivated successfully.",
        data=service.map_to_response(teacher),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Teacher Profile",
)
async def lock_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.lock")
    service = _make_service(db)
    teacher = await service.lock_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile locked successfully.",
        data=service.map_to_response(teacher),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Teacher Profile",
)
async def unlock_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.lock")
    service = _make_service(db)
    teacher = await service.unlock_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile unlocked successfully.",
        data=service.map_to_response(teacher),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[TeacherResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Teacher Profile",
)
async def archive_teacher(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TeacherResponse]:
    require_permission(current_user, "teacher.archive")
    service = _make_service(db)
    teacher = await service.archive_teacher_profile(
        teacher_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(teacher)

    return SuccessResponse[TeacherResponse](
        message="Teacher profile archived successfully.",
        data=service.map_to_response(teacher),
    )
