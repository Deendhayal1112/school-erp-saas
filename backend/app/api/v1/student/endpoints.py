"""
Student REST API Endpoints — Phase 4 Step 2.

All business logic is delegated to StudentService.
This layer handles:
  - HTTP request/response marshalling
  - Dependency injection (DB session, service, auth)
  - RBAC permission enforcement
  - Swagger documentation
"""

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
from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.repository import StudentRepository
from app.modules.student.schemas import (
    StudentCreate,
    StudentResponse,
    StudentSummary,
    StudentUpdate,
)
from app.modules.student.service import StudentService

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency Helpers
# ---------------------------------------------------------------------------


def _make_service(db: AsyncSession) -> StudentService:
    """Builds a StudentService from a shared AsyncSession."""
    return StudentService(StudentRepository(db), db)


def require_permission(user: User, code: str) -> None:
    """
    Enforces RBAC permission check on the active user.
    Raises ForbiddenException if the user's role does not hold the required permission code.
    """
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(
            f"Insufficient permissions. Required: '{code}'."
        )


# ---------------------------------------------------------------------------
# POST /students — Enroll a new student
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=CreatedResponse[StudentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Enroll a new student",
    description=(
        "Creates a new student record within the authenticated user's school tenant. "
        "Enforces admission number uniqueness, age constraints (2-30 years), "
        "E.164 phone format, 12-digit Aadhaar, and date validity rules."
    ),
    responses={
        201: {"description": "Student enrolled successfully."},
        400: {"description": "Invalid date, age, or format violation."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.create' required."},
        409: {"description": "Admission number or email already registered."},
        422: {"description": "Request body schema validation error."},
    },
    tags=["Students"],
)
async def create_student(
    body: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentResponse]:
    require_permission(current_user, "student.create")
    service = _make_service(db)
    student = await service.create_student(body)
    await db.commit()
    await db.refresh(student)
    return CreatedResponse[StudentResponse](
        message="Student enrolled successfully.",
        data=StudentResponse.model_validate(student),
    )


# ---------------------------------------------------------------------------
# GET /students — List students with pagination, filtering, and search
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=PaginatedResponse[StudentSummary],
    status_code=status.HTTP_200_OK,
    summary="List students",
    description=(
        "Returns a paginated, filterable, and searchable list of students within the "
        "authenticated user's school tenant. Supports filtering by status and gender, "
        "and free-text search across name, email, and admission number."
    ),
    responses={
        200: {"description": "Students retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.view' required."},
    },
    tags=["Students"],
)
async def list_students(
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed).")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Records per page.")] = 20,
    search: Annotated[str | None, Query(description="Free-text search on name, email, admission number.")] = None,
    status_filter: Annotated[StudentStatus | None, Query(alias="status", description="Filter by student status.")] = None,
    gender: Annotated[Gender | None, Query(description="Filter by gender.")] = None,
    sort: Annotated[str, Query(description="Sort field (default: created_at).")] = "created_at",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[StudentSummary]:
    require_permission(current_user, "student.view")
    service = _make_service(db)

    school_id = current_user.school_id
    params = PageParams(page=page, page_size=page_size)

    if search:
        # Full-text search path — bypass standard filter
        students = await service.repo.search(school_id, search)
        total = len(students)
        start = (page - 1) * page_size
        end = start + page_size
        page_students = students[start:end]
        total_pages = max(1, -(-total // page_size))  # Ceiling division
        summaries = [StudentSummary.model_validate(s) for s in page_students]
        return PaginatedResponse[StudentSummary](
            message="Students retrieved successfully.",
            results=summaries,
            pagination=PaginationMetadata(
                total_records=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                next=None,
                previous=None,
            ),
        )

    # Filter path via paginate()
    filters: dict[str, Any] = {}
    if status_filter is not None:
        filters["status"] = status_filter
    if gender is not None:
        filters["gender"] = gender

    paginated = await service.repo.paginate(
        school_id=school_id,
        params=params,
        filters=filters or None,
    )

    summaries = [StudentSummary.model_validate(s) for s in paginated["results"]]
    meta = paginated["pagination"]

    return PaginatedResponse[StudentSummary](
        message="Students retrieved successfully.",
        results=summaries,
        pagination=PaginationMetadata(**meta),
    )


# ---------------------------------------------------------------------------
# GET /students/{student_id} — Retrieve a single student
# ---------------------------------------------------------------------------


@router.get(
    "/{student_id}",
    response_model=SuccessResponse[StudentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get student by ID",
    description="Returns the full profile of a single student by their UUID.",
    responses={
        200: {"description": "Student profile retrieved."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.view' required."},
        404: {"description": "Student not found."},
    },
    tags=["Students"],
)
async def get_student(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[StudentResponse]:
    require_permission(current_user, "student.view")
    service = _make_service(db)
    student = await service.repo.get_by_id(student_id)
    if not student:
        raise StudentNotFoundException()
    return SuccessResponse[StudentResponse](
        message="Student profile retrieved successfully.",
        data=StudentResponse.model_validate(student),
    )


# ---------------------------------------------------------------------------
# PUT /students/{student_id} — Update a student record
# ---------------------------------------------------------------------------


@router.put(
    "/{student_id}",
    response_model=UpdatedResponse[StudentResponse],
    status_code=status.HTTP_200_OK,
    summary="Update student",
    description=(
        "Updates personal information, status, contact details, or remarks for a student. "
        "Status transitions are validated (e.g., cannot revert back to NEW once progressed). "
        "Admission number and email uniqueness are re-enforced on change."
    ),
    responses={
        200: {"description": "Student updated successfully."},
        400: {"description": "Invalid status transition or date constraint violation."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.update' required."},
        404: {"description": "Student not found."},
        409: {"description": "Admission number or email conflict."},
        422: {"description": "Request body schema validation error."},
    },
    tags=["Students"],
)
async def update_student(
    student_id: uuid.UUID,
    body: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[StudentResponse]:
    require_permission(current_user, "student.update")
    service = _make_service(db)
    updated = await service.update_student(student_id, body)
    await db.commit()
    await db.refresh(updated)
    return UpdatedResponse[StudentResponse](
        message="Student updated successfully.",
        data=StudentResponse.model_validate(updated),
    )


# ---------------------------------------------------------------------------
# DELETE /students/{student_id} — Soft-delete a student
# ---------------------------------------------------------------------------


@router.delete(
    "/{student_id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete student",
    description=(
        "Performs a soft delete on the student record. The record is hidden from "
        "standard queries but can be restored via the restore endpoint. "
        "No data is permanently removed."
    ),
    responses={
        200: {"description": "Student soft-deleted successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.delete' required."},
        404: {"description": "Student not found."},
    },
    tags=["Students"],
)
async def delete_student(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "student.delete")
    service = _make_service(db)
    await service.delete_student(student_id)
    await db.commit()
    return DeletedResponse(message="Student record soft-deleted successfully.")


# ---------------------------------------------------------------------------
# POST /students/{student_id}/restore — Restore a soft-deleted student
# ---------------------------------------------------------------------------


@router.post(
    "/{student_id}/restore",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Restore soft-deleted student",
    description="Restores a previously soft-deleted student record back to active visibility.",
    responses={
        200: {"description": "Student restored successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.restore' required."},
        404: {"description": "Student not found or not deleted."},
    },
    tags=["Students"],
)
async def restore_student(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[None]:
    require_permission(current_user, "student.restore")
    service = _make_service(db)
    await service.restore_student(student_id)
    await db.commit()
    return SuccessResponse[None](message="Student record restored successfully.")
