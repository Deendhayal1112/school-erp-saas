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
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, File, Query, Response, UploadFile, status
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
from app.modules.student.models import Student
from app.modules.student.repository import StudentRepository
from app.modules.student.schemas import (
    BulkDeleteRequest,
    BulkExportRequest,
    BulkRestoreRequest,
    BulkStatusRequest,
    ImportSummaryResponse,
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
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


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
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Records per page.")
    ] = 20,
    search: Annotated[
        str | None,
        Query(
            description="Advanced search query across name, email, phone, roll, admission."
        ),
    ] = None,
    status_filter: Annotated[
        StudentStatus | None, Query(alias="status", description="Filter by status.")
    ] = None,
    gender: Annotated[Gender | None, Query(description="Filter by gender.")] = None,
    blood_group: Annotated[
        str | None, Query(description="Filter by blood group.")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active status.")
    ] = None,
    joined_date_from: Annotated[
        date | None, Query(description="Joined date range from.")
    ] = None,
    joined_date_to: Annotated[
        date | None, Query(description="Joined date range to.")
    ] = None,
    created_at_from: Annotated[
        datetime | None, Query(description="Created at range from.")
    ] = None,
    created_at_to: Annotated[
        datetime | None, Query(description="Created at range to.")
    ] = None,
    updated_at_from: Annotated[
        datetime | None, Query(description="Updated at range from.")
    ] = None,
    updated_at_to: Annotated[
        datetime | None, Query(description="Updated at range to.")
    ] = None,
    class_id: Annotated[
        uuid.UUID | None, Query(description="Placeholder filter for future class.")
    ] = None,
    section_id: Annotated[
        uuid.UUID | None, Query(description="Placeholder filter for future section.")
    ] = None,
    sort: Annotated[
        str, Query(description="Sort field (default: -created_at).")
    ] = "-created_at",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[StudentSummary]:
    require_permission(current_user, "student.view")
    service = _make_service(db)

    school_id = current_user.school_id
    params = PageParams(page=page, page_size=page_size)

    filters = {
        "status": status_filter,
        "gender": gender,
        "blood_group": blood_group,
        "is_active": is_active,
        "joined_date_from": joined_date_from,
        "joined_date_to": joined_date_to,
        "created_at_from": created_at_from,
        "created_at_to": created_at_to,
        "updated_at_from": updated_at_from,
        "updated_at_to": updated_at_to,
        "class_id": class_id,
        "section_id": section_id,
    }

    paginated = await service.repo.paginate(
        school_id=school_id,
        params=params,
        search=search,
        filters=filters,
        sort=sort,
    )

    summaries = [StudentSummary.model_validate(s) for s in paginated["results"]]
    meta = paginated["pagination"]

    return PaginatedResponse[StudentSummary](
        message="Students retrieved successfully.",
        results=summaries,
        pagination=PaginationMetadata(**meta),
    )


# ---------------------------------------------------------------------------
# GET /students/export — Export filtered student list
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="Export students list",
    description="Export a filtered and searched list of student records as CSV, Excel, or PDF placeholder.",
    responses={
        200: {"description": "File downloaded successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.view' required."},
    },
    tags=["Students"],
)
async def export_students(
    search: Annotated[str | None, Query(description="Advanced search query.")] = None,
    status_filter: Annotated[
        StudentStatus | None, Query(alias="status", description="Filter by status.")
    ] = None,
    gender: Annotated[Gender | None, Query(description="Filter by gender.")] = None,
    blood_group: Annotated[
        str | None, Query(description="Filter by blood group.")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active status.")
    ] = None,
    joined_date_from: Annotated[
        date | None, Query(description="Joined date range from.")
    ] = None,
    joined_date_to: Annotated[
        date | None, Query(description="Joined date range to.")
    ] = None,
    created_at_from: Annotated[
        datetime | None, Query(description="Created at range from.")
    ] = None,
    created_at_to: Annotated[
        datetime | None, Query(description="Created at range to.")
    ] = None,
    updated_at_from: Annotated[
        datetime | None, Query(description="Updated at range from.")
    ] = None,
    updated_at_to: Annotated[
        datetime | None, Query(description="Updated at range to.")
    ] = None,
    class_id: Annotated[
        uuid.UUID | None, Query(description="Placeholder class filter.")
    ] = None,
    section_id: Annotated[
        uuid.UUID | None, Query(description="Placeholder section filter.")
    ] = None,
    sort: Annotated[str, Query(description="Sort query.")] = "-created_at",
    format: Annotated[
        str, Query(description="Export format: 'csv', 'excel', or 'pdf'.")
    ] = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "student.view")

    from sqlalchemy import select

    stmt = select(Student).where(
        Student.school_id == current_user.school_id, Student.is_deleted == False
    )

    # Apply search
    if search:
        from sqlalchemy import or_

        term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Student.first_name.ilike(term),
                Student.middle_name.ilike(term),
                Student.last_name.ilike(term),
                Student.admission_number.ilike(term),
                Student.roll_number.ilike(term),
                Student.email.ilike(term),
                Student.phone.ilike(term),
            )
        )

    # Apply filters
    filters = {
        "status": status_filter,
        "gender": gender,
        "blood_group": blood_group,
        "is_active": is_active,
        "joined_date_from": joined_date_from,
        "joined_date_to": joined_date_to,
        "created_at_from": created_at_from,
        "created_at_to": created_at_to,
        "updated_at_from": updated_at_from,
        "updated_at_to": updated_at_to,
        "class_id": class_id,
        "section_id": section_id,
    }

    for key, val in filters.items():
        if val is None:
            continue
        if key == "joined_date_from":
            stmt = stmt.where(Student.joined_date >= val)
        elif key == "joined_date_to":
            stmt = stmt.where(Student.joined_date <= val)
        elif key == "created_at_from":
            stmt = stmt.where(Student.created_at >= val)
        elif key == "created_at_to":
            stmt = stmt.where(Student.created_at <= val)
        elif key == "updated_at_from":
            stmt = stmt.where(Student.updated_at >= val)
        elif key == "updated_at_to":
            stmt = stmt.where(Student.updated_at <= val)
        elif key in ("class_id", "section_id"):
            if hasattr(Student, key):
                stmt = stmt.where(getattr(Student, key) == val)
        elif hasattr(Student, key):
            stmt = stmt.where(getattr(Student, key) == val)

    # Apply sorting
    from app.common.sorting import apply_sorting

    sortable = [
        "first_name",
        "last_name",
        "admission_number",
        "joined_date",
        "created_at",
        "updated_at",
    ]
    stmt = apply_sorting(stmt, Student, sort, sortable, default_sort="-created_at")

    res = await db.execute(stmt)
    students = list(res.scalars().all())

    return generate_file_response(students, format, "students_export")


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
    if not student or student.school_id != current_user.school_id:
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
    student = await service.repo.get_by_id(student_id)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()
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
    student = await service.repo.get_by_id(student_id)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()
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
    student = await service.repo.get_by_id(student_id, include_deleted=True)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()
    await service.restore_student(student_id)
    await db.commit()
    return SuccessResponse[None](message="Student record restored successfully.")


# ---------------------------------------------------------------------------
# POST /students/bulk-delete — Bulk soft-delete students
# ---------------------------------------------------------------------------


@router.post(
    "/bulk-delete",
    response_model=SuccessResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Bulk soft-delete students",
    description="Soft-deletes multiple students at once. Tenant isolated.",
    responses={
        200: {"description": "Bulk delete completed."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.delete' required."},
    },
    tags=["Students"],
)
async def bulk_delete_students(
    body: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[dict[str, Any]]:
    require_permission(current_user, "student.delete")
    service = _make_service(db)
    async with db.begin_nested():
        count = await service.bulk_delete_students(
            body.student_ids, current_user.school_id
        )
    await db.commit()
    return SuccessResponse[dict[str, Any]](
        message="Bulk delete completed.",
        data={"count": count},
    )


# ---------------------------------------------------------------------------
# POST /students/bulk-restore — Bulk restore soft-deleted students
# ---------------------------------------------------------------------------


@router.post(
    "/bulk-restore",
    response_model=SuccessResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Bulk restore students",
    description="Restores multiple soft-deleted students at once. Tenant isolated.",
    responses={
        200: {"description": "Bulk restore completed."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.restore' required."},
    },
    tags=["Students"],
)
async def bulk_restore_students(
    body: BulkRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[dict[str, Any]]:
    require_permission(current_user, "student.restore")
    service = _make_service(db)
    async with db.begin_nested():
        count = await service.bulk_restore_students(
            body.student_ids, current_user.school_id
        )
    await db.commit()
    return SuccessResponse[dict[str, Any]](
        message="Bulk restore completed.",
        data={"count": count},
    )


# ---------------------------------------------------------------------------
# POST /students/bulk-status — Bulk update student status
# ---------------------------------------------------------------------------


@router.post(
    "/bulk-status",
    response_model=SuccessResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Bulk update student status",
    description="Updates status of multiple students at once. Tenant isolated.",
    responses={
        200: {"description": "Bulk status update completed."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.update' required."},
    },
    tags=["Students"],
)
async def bulk_status_students(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[dict[str, Any]]:
    require_permission(current_user, "student.update")
    service = _make_service(db)
    async with db.begin_nested():
        count = await service.bulk_update_status(
            body.student_ids, body.status, current_user.school_id
        )
    await db.commit()
    return SuccessResponse[dict[str, Any]](
        message="Bulk status update completed.",
        data={"count": count},
    )


# ---------------------------------------------------------------------------
# POST /students/bulk-export — Bulk export selected students
# ---------------------------------------------------------------------------


@router.post(
    "/bulk-export",
    summary="Bulk export selected students",
    description="Export a list of student records matching specified UUIDs as CSV or Excel.",
    responses={
        200: {"description": "File downloaded successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.view' required."},
    },
    tags=["Students"],
)
async def bulk_export_students(
    body: BulkExportRequest,
    format: Annotated[
        str, Query(description="Export format: 'csv' or 'excel'.")
    ] = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    require_permission(current_user, "student.view")
    from sqlalchemy import select

    stmt = (
        select(Student)
        .where(
            Student.school_id == current_user.school_id,
            Student.is_deleted == False,
            Student.id.in_(body.student_ids),
        )
        .order_by(Student.created_at.desc())
    )

    res = await db.execute(stmt)
    students = list(res.scalars().all())

    return generate_file_response(students, format, "students_bulk_export")


# ---------------------------------------------------------------------------
# POST /students/import — Import students from CSV or Excel
# ---------------------------------------------------------------------------


@router.post(
    "/import",
    response_model=CreatedResponse[ImportSummaryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Import students from CSV or Excel",
    description="Imports a list of student records from a CSV or Excel (.xlsx) file. Performs full tenant isolation, field validation, and database duplicate checks. Valid records are committed; critical failures trigger rollback.",
    responses={
        201: {"description": "Import batch processed successfully."},
        400: {"description": "Invalid file format or parsing error."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.create' required."},
    },
    tags=["Students"],
)
async def import_students(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[ImportSummaryResponse]:
    require_permission(current_user, "student.create")
    service = _make_service(db)

    content = await file.read()

    async with db.begin_nested():
        summary = await service.import_students(
            content, file.filename or "file.csv", current_user.school_id
        )

    await db.commit()

    return CreatedResponse[ImportSummaryResponse](
        message="Import batch processed.",
        data=ImportSummaryResponse.model_validate(summary),
    )


# ---------------------------------------------------------------------------
# File Generation Helper
# ---------------------------------------------------------------------------


def generate_file_response(
    students: list[Student], format: str, base_filename: str
) -> Response:
    import csv
    import io

    import openpyxl

    from app.exceptions.exceptions import BadRequestException

    headers = [
        "admission_number",
        "roll_number",
        "emis_number",
        "first_name",
        "middle_name",
        "last_name",
        "gender",
        "date_of_birth",
        "blood_group",
        "email",
        "phone",
        "aadhaar_number",
        "nationality",
        "religion",
        "caste",
        "community",
        "mother_tongue",
        "photo_url",
        "joined_date",
        "graduation_date",
        "status",
        "is_active",
        "remarks",
        "created_at",
        "updated_at",
    ]

    fmt = format.lower()
    if fmt == "csv":
        csv_stream = io.StringIO()
        writer = csv.writer(csv_stream)
        writer.writerow(headers)
        for s in students:
            writer.writerow(
                [
                    s.admission_number,
                    s.roll_number,
                    s.emis_number,
                    s.first_name,
                    s.middle_name,
                    s.last_name,
                    s.gender.value if s.gender else "",
                    str(s.date_of_birth) if s.date_of_birth else "",
                    s.blood_group,
                    s.email,
                    s.phone,
                    s.aadhaar_number,
                    s.nationality,
                    s.religion,
                    s.caste,
                    s.community,
                    s.mother_tongue,
                    s.photo_url,
                    str(s.joined_date) if s.joined_date else "",
                    str(s.graduation_date) if s.graduation_date else "",
                    s.status.value if s.status else "",
                    str(s.is_active),
                    s.remarks,
                    s.created_at.isoformat() if s.created_at else "",
                    s.updated_at.isoformat() if s.updated_at else "",
                ]
            )
        response = Response(content=csv_stream.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename={base_filename}.csv"
        )
        return response

    elif fmt in ("excel", "xlsx"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.append(headers)
        for s in students:
            ws.append(
                [
                    s.admission_number,
                    s.roll_number,
                    s.emis_number,
                    s.first_name,
                    s.middle_name,
                    s.last_name,
                    s.gender.value if s.gender else "",
                    str(s.date_of_birth) if s.date_of_birth else "",
                    s.blood_group,
                    s.email,
                    s.phone,
                    s.aadhaar_number,
                    s.nationality,
                    s.religion,
                    s.caste,
                    s.community,
                    s.mother_tongue,
                    s.photo_url,
                    str(s.joined_date) if s.joined_date else "",
                    str(s.graduation_date) if s.graduation_date else "",
                    s.status.value if s.status else "",
                    s.is_active,
                    s.remarks,
                    s.created_at.isoformat() if s.created_at else "",
                    s.updated_at.isoformat() if s.updated_at else "",
                ]
            )
        excel_stream = io.BytesIO()
        wb.save(excel_stream)
        response = Response(
            content=excel_stream.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["Content-Disposition"] = (
            f"attachment; filename={base_filename}.xlsx"
        )
        return response

    elif fmt == "pdf":
        mock_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Students Export Placeholder) >>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        response = Response(content=mock_pdf, media_type="application/pdf")
        response.headers["Content-Disposition"] = (
            f"attachment; filename={base_filename}.pdf"
        )
        return response

    else:
        raise BadRequestException(f"Unsupported export format: {format}")


# ===========================================================================
# Student-Guardian Mapping APIs — Task 8
# ===========================================================================


@router.post(
    "/{student_id}/guardians",
    response_model=CreatedResponse[Any],
    status_code=status.HTTP_201_CREATED,
    summary="Map student to guardian",
    description="Maps a student to a guardian, enforcing primary flag singularity rules.",
    responses={
        201: {"description": "Mapping created successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.guardian.manage' required."},
        404: {"description": "Student or Guardian not found."},
    },
    tags=["Students"],
)
async def map_student_guardian(
    student_id: uuid.UUID,
    body: Any = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[Any]:
    from app.modules.guardian.schemas import (
        StudentGuardianMappingCreate,
        StudentGuardianMappingResponse,
    )
    from app.modules.guardian.service import GuardianService

    require_permission(current_user, "student.guardian.manage")

    schema = StudentGuardianMappingCreate.model_validate(body)

    # 1. Enforce student existence & tenant context
    student_service = _make_service(db)
    student = await student_service.repo.get_by_id(student_id)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()

    guardian_service = GuardianService(db)
    mapping = await guardian_service.map_student_to_guardian(
        student_id, schema, current_user.school_id
    )
    await db.commit()
    await db.refresh(mapping)

    return CreatedResponse[Any](
        message="Student guardian mapping created successfully.",
        data=StudentGuardianMappingResponse.model_validate(mapping),
    )


@router.get(
    "/{student_id}/guardians",
    response_model=SuccessResponse[list[Any]],
    status_code=status.HTTP_200_OK,
    summary="Get student's mapped guardians",
    description="Retrieves a list of all guardians mapped to the student.",
    responses={
        200: {"description": "List of mapped guardians retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'guardian.read' required."},
        404: {"description": "Student not found."},
    },
    tags=["Students"],
)
async def get_student_guardians(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[Any]]:
    from app.modules.guardian.schemas import StudentGuardianMappingResponse
    from app.modules.guardian.service import GuardianService

    require_permission(current_user, "guardian.read")

    # 1. Enforce student existence & tenant context
    student_service = _make_service(db)
    student = await student_service.repo.get_by_id(student_id)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()

    guardian_service = GuardianService(db)
    mappings = await guardian_service.get_mapped_guardians(
        student_id, current_user.school_id
    )

    return SuccessResponse[list[Any]](
        message="Mapped guardians retrieved successfully.",
        data=[StudentGuardianMappingResponse.model_validate(m) for m in mappings],
    )


@router.delete(
    "/{student_id}/guardians/{guardian_id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Unmap a student and guardian",
    description="Removes the mapping association between student and guardian.",
    responses={
        200: {"description": "Mapping removed successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.guardian.manage' required."},
        404: {"description": "Mapping, Student or Guardian not found."},
    },
    tags=["Students"],
)
async def unmap_student_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    from app.modules.guardian.service import GuardianService

    require_permission(current_user, "student.guardian.manage")

    # 1. Enforce student existence & tenant context
    student_service = _make_service(db)
    student = await student_service.repo.get_by_id(student_id)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()

    guardian_service = GuardianService(db)
    await guardian_service.unmap_student_guardian(
        student_id, guardian_id, current_user.school_id
    )
    await db.commit()

    return DeletedResponse(message="Student guardian mapping removed successfully.")


@router.patch(
    "/{student_id}/guardians/{guardian_id}",
    response_model=UpdatedResponse[Any],
    status_code=status.HTTP_200_OK,
    summary="Update student-guardian mapping details",
    description="Updates parameters on the mapping between student and guardian.",
    responses={
        200: {"description": "Mapping updated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.guardian.manage' required."},
        404: {"description": "Mapping, Student or Guardian not found."},
    },
    tags=["Students"],
)
async def update_student_guardian_mapping(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    body: Any = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[Any]:
    from app.modules.guardian.schemas import (
        StudentGuardianMappingResponse,
        StudentGuardianMappingUpdate,
    )
    from app.modules.guardian.service import GuardianService

    require_permission(current_user, "student.guardian.manage")

    schema = StudentGuardianMappingUpdate.model_validate(body)

    # 1. Enforce student existence & tenant context
    student_service = _make_service(db)
    student = await student_service.repo.get_by_id(student_id)
    if not student or student.school_id != current_user.school_id:
        raise StudentNotFoundException()

    guardian_service = GuardianService(db)
    mapping = await guardian_service.update_mapping(
        student_id, guardian_id, schema, current_user.school_id
    )
    await db.commit()
    await db.refresh(mapping)

    return UpdatedResponse[Any](
        message="Student guardian mapping updated successfully.",
        data=StudentGuardianMappingResponse.model_validate(mapping),
    )
