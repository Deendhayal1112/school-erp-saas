import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams
from app.common.responses import (
    CreatedResponse,
    DeletedResponse,
    PaginatedResponse,
    PaginationMetadata,
    SuccessResponse,
    UpdatedResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.guardian.enums import Relationship
from app.modules.guardian.exceptions import GuardianNotFoundException
from app.modules.guardian.schemas import (
    GuardianCreate,
    GuardianResponse,
    GuardianUpdate,
)
from app.modules.guardian.service import GuardianService

router = APIRouter()


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


def _make_service(db: AsyncSession) -> GuardianService:
    return GuardianService(db)


@router.post(
    "/",
    response_model=CreatedResponse[GuardianResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new guardian record",
    description="Registers a new guardian under the active user's school tenant.",
    responses={
        201: {"description": "Guardian created successfully."},
        400: {"description": "Validation or constraint check failure."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.create' required."},
        409: {"description": "Duplicate phone, email or Aadhaar contact details."},
    },
)
async def create_guardian(
    body: GuardianCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[GuardianResponse]:
    require_permission(current_user, "guardian.create")

    # Enforce tenant isolation
    body.school_id = current_user.school_id

    service = _make_service(db)
    guardian = await service.create_guardian(body)
    await db.commit()
    await db.refresh(guardian)

    return CreatedResponse[GuardianResponse](
        message="Guardian record created successfully.",
        data=GuardianResponse.model_validate(guardian),
    )


@router.get(
    "/",
    response_model=PaginatedResponse[GuardianResponse],
    status_code=status.HTTP_200_OK,
    summary="List and search guardians",
    description="Retrieve a paginated, sorted, and filtered list of guardians within the user's school tenant.",
    responses={
        200: {"description": "Guardians list retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.read' required."},
    },
)
async def list_guardians(
    page: Annotated[int, Query(ge=1, description="Page index.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size limit.")] = 10,
    search: Annotated[str | None, Query(description="Wildcard search term.")] = None,
    relationship: Annotated[
        Relationship | None, Query(description="Filter by relationship.")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active status.")
    ] = None,
    sort: Annotated[str, Query(description="Sorting criteria.")] = "-created_at",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[GuardianResponse]:
    require_permission(current_user, "guardian.read")
    service = _make_service(db)

    params = PageParams(page=page, page_size=page_size)
    filters: dict[str, Any] = {}
    if relationship is not None:
        filters["relationship"] = relationship
    if is_active is not None:
        filters["is_active"] = is_active

    paginated = await service.repo.paginate(
        school_id=current_user.school_id,
        params=params,
        search=search,
        filters=filters,
        sort=sort,
    )

    summaries = [GuardianResponse.model_validate(g) for g in paginated["results"]]
    meta = paginated["pagination"]

    return PaginatedResponse[GuardianResponse](
        message="Guardians retrieved successfully.",
        results=summaries,
        pagination=PaginationMetadata(**meta),
    )


@router.get(
    "/{guardian_id}",
    response_model=SuccessResponse[GuardianResponse],
    status_code=status.HTTP_200_OK,
    summary="Get guardian by ID",
    description="Retrieve full details of a specific guardian record. Tenant isolated.",
    responses={
        200: {"description": "Guardian profile retrieved."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.read' required."},
        404: {"description": "Guardian not found."},
    },
)
async def get_guardian(
    guardian_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[GuardianResponse]:
    require_permission(current_user, "guardian.read")
    service = _make_service(db)
    guardian = await service.repo.get_by_id(guardian_id)
    if not guardian or guardian.school_id != current_user.school_id:
        raise GuardianNotFoundException()

    return SuccessResponse[GuardianResponse](
        message="Guardian profile retrieved successfully.",
        data=GuardianResponse.model_validate(guardian),
    )


@router.put(
    "/{guardian_id}",
    response_model=UpdatedResponse[GuardianResponse],
    status_code=status.HTTP_200_OK,
    summary="Update guardian by ID",
    description="Updates information of a specific guardian. Tenant isolated.",
    responses={
        200: {"description": "Guardian details updated successfully."},
        400: {"description": "Validation checks failure."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.update' required."},
        404: {"description": "Guardian not found."},
        409: {"description": "Duplicate phone, email or Aadhaar contact details."},
    },
)
async def update_guardian(
    guardian_id: uuid.UUID,
    body: GuardianUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[GuardianResponse]:
    require_permission(current_user, "guardian.update")
    service = _make_service(db)

    updated = await service.update_guardian(guardian_id, body, current_user.school_id)
    await db.commit()
    await db.refresh(updated)

    return UpdatedResponse[GuardianResponse](
        message="Guardian details updated successfully.",
        data=GuardianResponse.model_validate(updated),
    )


@router.delete(
    "/{guardian_id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete guardian by ID",
    description="Soft-deletes a guardian from the system context. Tenant isolated.",
    responses={
        200: {"description": "Guardian soft-deleted successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.delete' required."},
        404: {"description": "Guardian not found."},
    },
)
async def delete_guardian(
    guardian_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "guardian.delete")
    service = _make_service(db)
    await service.delete_guardian(guardian_id, current_user.school_id)
    await db.commit()
    return DeletedResponse(message="Guardian record soft-deleted successfully.")


@router.post(
    "/{guardian_id}/restore",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Restore a soft-deleted guardian",
    description="Restores a previously soft-deleted guardian record back to visibility. Tenant isolated.",
    responses={
        200: {"description": "Guardian record restored successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.restore' required."},
        404: {"description": "Guardian not found."},
    },
)
async def restore_guardian(
    guardian_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[None]:
    require_permission(current_user, "guardian.restore")
    service = _make_service(db)
    await service.restore_guardian(guardian_id, current_user.school_id)
    await db.commit()
    return SuccessResponse[None](message="Guardian record restored successfully.")
