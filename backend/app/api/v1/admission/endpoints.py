import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams
from app.common.responses import (
    CreatedResponse,
    PaginatedResponse,
    PaginationMetadata,
    SuccessResponse,
    UpdatedResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.admission.enums import AdmissionStatus
from app.modules.admission.exceptions import AdmissionNotFoundException
from app.modules.admission.schemas import (
    AdmissionActionRequest,
    AdmissionCreate,
    AdmissionRejectRequest,
    AdmissionResponse,
    AdmissionUpdate,
)
from app.modules.admission.service import AdmissionService

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


def _make_service(db: AsyncSession) -> AdmissionService:
    return AdmissionService(db)


@router.post(
    "/",
    response_model=CreatedResponse[AdmissionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new admission application",
    description="Registers a new student admission application in DRAFT state.",
    responses={
        201: {"description": "Admission draft created successfully."},
        400: {"description": "Validation or duplicate application checks fail."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.create' required."},
    },
)
async def create_admission(
    body: AdmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AdmissionResponse]:
    require_permission(current_user, "admission.create")
    service = _make_service(db)

    admission = await service.create_application(body, current_user.school_id)
    await db.commit()
    await db.refresh(admission)

    return CreatedResponse[AdmissionResponse](
        message="Admission application draft created successfully.",
        data=AdmissionResponse.model_validate(admission),
    )


@router.get(
    "/",
    response_model=PaginatedResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="List and search admission applications",
    description="Lists all admission applications within the user's school tenant.",
    responses={
        200: {"description": "List of admissions retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.read' required."},
    },
)
async def list_admissions(
    page: Annotated[int, Query(ge=1, description="Page index.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size limit.")] = 10,
    search: Annotated[str | None, Query(description="Wildcard search term.")] = None,
    status: Annotated[
        AdmissionStatus | None, Query(description="Filter by admission status.")
    ] = None,
    academic_year: Annotated[
        str | None, Query(description="Filter by academic year.")
    ] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[AdmissionResponse]:
    require_permission(current_user, "admission.read")
    service = _make_service(db)

    params = PageParams(page=page, page_size=page_size)
    filters: dict[str, Any] = {}
    if status is not None:
        filters["status"] = status
    if academic_year is not None:
        filters["academic_year"] = academic_year

    paginated = await service.repo.paginate(
        school_id=current_user.school_id,
        params=params,
        search=search,
        filters=filters,
    )

    summaries = [AdmissionResponse.model_validate(a) for a in paginated["results"]]
    meta = paginated["pagination"]

    return PaginatedResponse[AdmissionResponse](
        message="Admissions retrieved successfully.",
        results=summaries,
        pagination=PaginationMetadata(**meta),
    )


@router.get(
    "/{admission_id}",
    response_model=SuccessResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get admission application details",
    description="Retrieve details of a specific application including its complete timeline audit logs.",
    responses={
        200: {"description": "Admission details retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.read' required."},
        404: {"description": "Admission application not found."},
    },
)
async def get_admission(
    admission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AdmissionResponse]:
    require_permission(current_user, "admission.read")
    service = _make_service(db)

    admission = await service.repo.get_admission_by_id(admission_id)
    if not admission or admission.school_id != current_user.school_id:
        raise AdmissionNotFoundException()

    return SuccessResponse[AdmissionResponse](
        message="Admission details retrieved successfully.",
        data=AdmissionResponse.model_validate(admission),
    )


@router.put(
    "/{admission_id}",
    response_model=UpdatedResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Update admission application details",
    description="Updates information parameters on a draft or pending application. Tenant isolated.",
    responses={
        200: {"description": "Admission details updated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.update' required."},
        404: {"description": "Admission not found."},
    },
)
async def update_admission(
    admission_id: uuid.UUID,
    body: AdmissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[AdmissionResponse]:
    require_permission(current_user, "admission.update")
    service = _make_service(db)

    updated = await service.update_application(
        admission_id, body, current_user.school_id
    )
    await db.commit()
    await db.refresh(updated)

    return UpdatedResponse[AdmissionResponse](
        message="Admission application details updated successfully.",
        data=AdmissionResponse.model_validate(updated),
    )


@router.post(
    "/{admission_id}/submit",
    response_model=SuccessResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Submit admission application",
    description="Submits the application for administrative review. Enforces guardian validation checks.",
    responses={
        200: {"description": "Application submitted successfully."},
        400: {"description": "Submission pre-conditions (e.g. guardian mapped) fail."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.submit' required."},
        404: {"description": "Admission not found."},
    },
)
async def submit_admission(
    admission_id: uuid.UUID,
    body: AdmissionActionRequest = Body(default_factory=AdmissionActionRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AdmissionResponse]:
    require_permission(current_user, "admission.submit")
    service = _make_service(db)

    admission = await service.submit_application(
        admission_id=admission_id,
        user_id=current_user.id,
        school_id=current_user.school_id,
        remarks=body.remarks,
    )
    await db.commit()
    await db.refresh(admission)

    return SuccessResponse[AdmissionResponse](
        message="Admission application submitted successfully.",
        data=AdmissionResponse.model_validate(admission),
    )


@router.post(
    "/{admission_id}/approve",
    response_model=SuccessResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Approve admission application",
    description="Approves the application. Enforces document verification checks.",
    responses={
        200: {"description": "Application approved successfully."},
        400: {"description": "Documents not verified or other checks fail."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.approve' required."},
        404: {"description": "Admission not found."},
    },
)
async def approve_admission(
    admission_id: uuid.UUID,
    body: AdmissionActionRequest = Body(default_factory=AdmissionActionRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AdmissionResponse]:
    require_permission(current_user, "admission.approve")
    service = _make_service(db)

    admission = await service.approve_application(
        admission_id=admission_id,
        user_id=current_user.id,
        school_id=current_user.school_id,
        remarks=body.remarks,
    )
    await db.commit()
    await db.refresh(admission)

    return SuccessResponse[AdmissionResponse](
        message="Admission application approved successfully.",
        data=AdmissionResponse.model_validate(admission),
    )


@router.post(
    "/{admission_id}/reject",
    response_model=SuccessResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Reject admission application",
    description="Rejects the application with a mandatory rejection explanation.",
    responses={
        200: {"description": "Application rejected successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.reject' required."},
        404: {"description": "Admission not found."},
    },
)
async def reject_admission(
    admission_id: uuid.UUID,
    body: AdmissionRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AdmissionResponse]:
    require_permission(current_user, "admission.reject")
    service = _make_service(db)

    admission = await service.reject_application(
        admission_id=admission_id,
        user_id=current_user.id,
        school_id=current_user.school_id,
        rejection_reason=body.rejection_reason,
        remarks=body.remarks,
    )
    await db.commit()
    await db.refresh(admission)

    return SuccessResponse[AdmissionResponse](
        message="Admission application rejected successfully.",
        data=AdmissionResponse.model_validate(admission),
    )


@router.post(
    "/{admission_id}/enroll",
    response_model=SuccessResponse[AdmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Enroll approved applicant",
    description="Enrolls the student. Generates Admission Number, activates student profile.",
    responses={
        200: {"description": "Student enrolled successfully."},
        400: {"description": "Enrollment validations (e.g. fees paid) fail."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'admission.enroll' required."},
        404: {"description": "Admission not found."},
    },
)
async def enroll_admission(
    admission_id: uuid.UUID,
    body: AdmissionActionRequest = Body(default_factory=AdmissionActionRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AdmissionResponse]:
    require_permission(current_user, "admission.enroll")
    service = _make_service(db)

    admission = await service.enroll_student(
        admission_id=admission_id,
        user_id=current_user.id,
        school_id=current_user.school_id,
        remarks=body.remarks,
    )
    await db.commit()
    await db.refresh(admission)

    return SuccessResponse[AdmissionResponse](
        message="Student enrolled and admitted successfully.",
        data=AdmissionResponse.model_validate(admission),
    )
