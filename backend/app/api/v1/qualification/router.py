import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.qualification.enums import QualificationStatus, QualificationType
from app.modules.qualification.schemas import (
    QualificationCreate,
    QualificationResponse,
    QualificationUpdate,
)
from app.modules.qualification.service import QualificationService

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


def _make_service(db: AsyncSession) -> QualificationService:
    return QualificationService(db)


@router.post(
    "",
    response_model=CreatedResponse[QualificationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Qualification Record",
)
async def create_qualification(
    body: QualificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[QualificationResponse]:
    require_permission(current_user, "qualification.create")
    service = _make_service(db)
    q = await service.create_qualification(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(q)

    return CreatedResponse[QualificationResponse](
        message="Qualification record created successfully.",
        data=service.map_to_response(q),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[QualificationResponse]],
    status_code=status.HTTP_200_OK,
    summary="List/Search Qualifications",
)
async def list_qualifications(
    employee_id: Annotated[
        uuid.UUID | None, Query(description="Filter by employee ID")
    ] = None,
    qualification_type: Annotated[
        QualificationType | None, Query(description="Filter by qualification type")
    ] = None,
    institution_name: Annotated[
        str | None, Query(description="Filter by institution name (partial match)")
    ] = None,
    is_verified: Annotated[
        bool | None, Query(description="Filter by verification flag")
    ] = None,
    is_highest_qualification: Annotated[
        bool | None, Query(description="Filter by highest qualification flag")
    ] = None,
    passing_year: Annotated[
        int | None, Query(description="Filter by passing year")
    ] = None,
    status: Annotated[
        QualificationStatus | None, Query(description="Filter by status")
    ] = None,
    query: Annotated[
        str | None,
        Query(description="General query to search by name/degree/spec/inst"),
    ] = None,
    sort_by: Annotated[
        str | None, Query(description="Sort field name")
    ] = "passing_year",
    sort_dir: Annotated[
        str | None, Query(description="Sort direction (asc/desc)")
    ] = "desc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[QualificationResponse]]:
    require_permission(current_user, "qualification.read")
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
            qualification_type=qualification_type,
            institution_name=institution_name,
            is_verified=is_verified,
            is_highest_qualification=is_highest_qualification,
            passing_year=passing_year,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    return SuccessResponse[list[QualificationResponse]](
        message="Qualifications list retrieved successfully.",
        data=[service.map_to_response(i) for i in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/employee/{employee_id}",
    response_model=SuccessResponse[list[QualificationResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Qualifications by Employee ID",
)
async def get_qualifications_by_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[QualificationResponse]]:
    require_permission(current_user, "qualification.read")
    service = _make_service(db)
    items = await service.get_by_employee_cached(employee_id, current_user.school_id)

    return SuccessResponse[list[QualificationResponse]](
        message="Employee qualifications retrieved successfully.",
        data=items,
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Qualification by ID",
)
async def get_qualification_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.read")
    service = _make_service(db)
    resp = await service.get_by_id_cached(id, current_user.school_id)

    return SuccessResponse[QualificationResponse](
        message="Qualification details retrieved successfully.",
        data=resp,
    )


@router.put(
    "/{id}",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Qualification Details",
)
async def update_qualification(
    id: uuid.UUID,
    body: QualificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.update")
    service = _make_service(db)
    q = await service.update_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification details updated successfully.",
        data=service.map_to_response(q),
    )


@router.delete(
    "/{id}",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Delete (Soft-Delete) Qualification",
)
async def delete_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.delete")
    service = _make_service(db)
    q = await service.delete_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification record soft-deleted successfully.",
        data=service.map_to_response(q),
    )


@router.post(
    "/{id}/restore",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Qualification",
)
async def restore_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.delete")
    service = _make_service(db)
    q = await service.restore_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification record restored successfully.",
        data=service.map_to_response(q),
    )


@router.patch(
    "/{id}/verify",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify Qualification Record",
)
async def verify_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.verify")
    service = _make_service(db)
    q = await service.verify_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification record verified successfully.",
        data=service.map_to_response(q),
    )


@router.patch(
    "/{id}/activate",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate Qualification",
)
async def activate_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.activate")
    service = _make_service(db)
    q = await service.activate_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification activated successfully.",
        data=service.map_to_response(q),
    )


@router.patch(
    "/{id}/deactivate",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate Qualification",
)
async def deactivate_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.activate")
    service = _make_service(db)
    q = await service.deactivate_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification deactivated successfully.",
        data=service.map_to_response(q),
    )


@router.patch(
    "/{id}/lock",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Lock Qualification",
)
async def lock_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.activate")
    service = _make_service(db)
    q = await service.lock_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification locked successfully.",
        data=service.map_to_response(q),
    )


@router.patch(
    "/{id}/unlock",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Unlock Qualification",
)
async def unlock_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.activate")
    service = _make_service(db)
    q = await service.unlock_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification unlocked successfully.",
        data=service.map_to_response(q),
    )


@router.patch(
    "/{id}/archive",
    response_model=SuccessResponse[QualificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive Qualification",
)
async def archive_qualification(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[QualificationResponse]:
    require_permission(current_user, "qualification.archive")
    service = _make_service(db)
    q = await service.archive_qualification(
        q_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(q)

    return SuccessResponse[QualificationResponse](
        message="Qualification archived successfully.",
        data=service.map_to_response(q),
    )
