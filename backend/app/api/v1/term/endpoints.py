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
from app.modules.academic_year.service import AcademicYearService
from app.modules.term.enums import TermStatus
from app.modules.term.exceptions import TermNotFoundException
from app.modules.term.schemas import (
    TermCreate,
    TermResponse,
    TermUpdate,
)
from app.modules.term.service import TermService

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


def _make_service(db: AsyncSession) -> TermService:
    return TermService(db)


def _make_ay_service(db: AsyncSession) -> AcademicYearService:
    return AcademicYearService(db)


@router.post(
    "",
    response_model=CreatedResponse[TermResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Term/Semester",
    responses={
        201: {"description": "Term created successfully."},
        400: {"description": "Date range overlap, or unique code/name conflict."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'term.create' required."},
    },
)
async def create_term(
    body: TermCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[TermResponse]:
    require_permission(current_user, "term.create")
    service = _make_service(db)
    term = await service.create_term(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(term)

    return CreatedResponse[TermResponse](
        message="Term created successfully.",
        data=TermResponse.model_validate(term),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[TermResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Terms/Semesters",
)
async def list_terms(
    academic_year_id: Annotated[
        uuid.UUID | None, Query(description="Filter by Academic Year")
    ] = None,
    status_filter: Annotated[
        TermStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    name: Annotated[str | None, Query(description="Filter by name")] = None,
    code: Annotated[str | None, Query(description="Filter by code")] = None,
    term_number: Annotated[
        int | None, Query(description="Filter by term number")
    ] = None,
    search: Annotated[str | None, Query(description="General search name/code")] = None,
    sort_by: Annotated[str | None, Query(description="Sort field name")] = "start_date",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TermResponse]]:
    require_permission(current_user, "term.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_all(
        school_id=current_user.school_id,
        academic_year_id=academic_year_id,
        status=status_filter,
        name=name,
        code=code,
        term_number=term_number,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse[list[TermResponse]](
        message="Terms retrieved successfully.",
        data=[TermResponse.model_validate(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/active",
    response_model=SuccessResponse[TermResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get active Term for current active Academic Year",
)
async def get_active_term(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse | None]:
    require_permission(current_user, "term.read")
    ay_service = _make_ay_service(db)
    service = _make_service(db)

    ay = await ay_service.get_active_cached(current_user.school_id)
    if not ay:
        return SuccessResponse[TermResponse | None](
            message="No active academic year resolved.",
            data=None,
        )

    term = await service.get_active_cached(ay.id)
    return SuccessResponse[TermResponse | None](
        message="Active term resolved successfully.",
        data=TermResponse.model_validate(term) if term else None,
    )


@router.get(
    "/default",
    response_model=SuccessResponse[TermResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get default Term for default Academic Year",
)
async def get_default_term(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse | None]:
    require_permission(current_user, "term.read")
    ay_service = _make_ay_service(db)
    service = _make_service(db)

    ay = await ay_service.get_default_cached(current_user.school_id)
    if not ay:
        return SuccessResponse[TermResponse | None](
            message="No default academic year resolved.",
            data=None,
        )

    term = await service.get_default_cached(ay.id)
    return SuccessResponse[TermResponse | None](
        message="Default term resolved successfully.",
        data=TermResponse.model_validate(term) if term else None,
    )


@router.get(
    "/academic-year/{academic_year_id}",
    response_model=SuccessResponse[list[TermResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Terms by Academic Year ID",
)
async def get_terms_by_academic_year(
    academic_year_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TermResponse]]:
    require_permission(current_user, "term.read")
    service = _make_service(db)
    items = await service.get_by_academic_year_cached(academic_year_id)
    # Ensure multi-tenant security
    for item in items:
        if item.school_id != current_user.school_id:
            raise ForbiddenException(
                "Access to this academic year's terms is restricted."
            )

    return SuccessResponse[list[TermResponse]](
        message="Terms retrieved successfully.",
        data=[TermResponse.model_validate(i) for i in items],
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Term by ID",
)
async def get_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.read")
    service = _make_service(db)
    term = await service.repo.get_by_id(id)
    if not term or term.school_id != current_user.school_id:
        raise TermNotFoundException()

    return SuccessResponse[TermResponse](
        message="Term retrieved successfully.",
        data=TermResponse.model_validate(term),
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Term",
)
async def update_term(
    id: uuid.UUID,
    body: TermUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.update")
    service = _make_service(db)
    term = await service.update_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term updated successfully.",
        data=TermResponse.model_validate(term),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[bool],
    status_code=status.HTTP_200_OK,
    summary="Delete Term",
)
async def delete_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[bool]:
    require_permission(current_user, "term.delete")
    service = _make_service(db)
    res = await service.delete_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return SuccessResponse[bool](
        message="Term soft-deleted successfully.",
        data=res,
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Term",
)
async def activate_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.activate")
    service = _make_service(db)
    term = await service.activate_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term activated successfully.",
        data=TermResponse.model_validate(term),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Term",
)
async def deactivate_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.activate")
    service = _make_service(db)
    term = await service.deactivate_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term deactivated successfully.",
        data=TermResponse.model_validate(term),
    )


@router.patch(
    "/{id}/default",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Set default Term",
)
async def set_default_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.default")
    service = _make_service(db)
    term = await service.set_default_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term set as default successfully.",
        data=TermResponse.model_validate(term),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Term",
)
async def lock_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.lock")
    service = _make_service(db)
    term = await service.lock_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term locked successfully.",
        data=TermResponse.model_validate(term),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Term",
)
async def unlock_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.lock")
    service = _make_service(db)
    term = await service.unlock_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term unlocked successfully.",
        data=TermResponse.model_validate(term),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[TermResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Term",
)
async def archive_term(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TermResponse]:
    require_permission(current_user, "term.archive")
    service = _make_service(db)
    term = await service.archive_term(
        term_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(term)

    return SuccessResponse[TermResponse](
        message="Term archived successfully.",
        data=TermResponse.model_validate(term),
    )
