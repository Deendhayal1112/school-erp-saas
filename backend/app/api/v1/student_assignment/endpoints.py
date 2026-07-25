import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import (
    CreatedResponse,
    DeletedResponse,
    SuccessResponse,
    UpdatedResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.student_assignment.repository import (
    StudentAcademicAssignmentRepository,
)
from app.modules.student_assignment.schemas import (
    BulkAssignmentCreate,
    StudentAcademicAssignmentCreate,
    StudentAcademicAssignmentResponse,
    StudentAcademicAssignmentUpdate,
    TransferAssignmentRequest,
)
from app.modules.student_assignment.service import StudentAcademicAssignmentService

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


def _make_service(db: AsyncSession) -> StudentAcademicAssignmentService:
    return StudentAcademicAssignmentService(db)


@router.post(
    "",
    response_model=CreatedResponse[StudentAcademicAssignmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create student academic assignment",
    description="Assigns a student to class context and section.",
    responses={
        201: {"description": "Academic assignment completed successfully."},
        400: {"description": "Duplicate active assignment or roll number conflict."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.create' required."},
        404: {"description": "Student not found."},
    },
)
async def assign_student(
    body: StudentAcademicAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentAcademicAssignmentResponse]:
    require_permission(current_user, "student.assignment.create")
    service = _make_service(db)

    assignment = await service.assign_student(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(assignment)

    return CreatedResponse[StudentAcademicAssignmentResponse](
        message="Student assigned successfully.",
        data=StudentAcademicAssignmentResponse.model_validate(assignment),
    )


@router.get(
    "",
    response_model=SuccessResponse[list[StudentAcademicAssignmentResponse]],
    status_code=status.HTTP_200_OK,
    summary="List student assignments",
    description="Retrieves a list of student academic assignments filtered by class or section.",
    responses={
        200: {"description": "Assignments list retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.read' required."},
    },
)
async def list_assignments(
    class_id: uuid.UUID | None = Query(None, description="Filter by class"),
    section_id: uuid.UUID | None = Query(None, description="Filter by section"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[StudentAcademicAssignmentResponse]]:
    require_permission(current_user, "student.assignment.read")
    repo = StudentAcademicAssignmentRepository(db)

    if section_id:
        results = await repo.get_by_section(section_id)
    elif class_id:
        results = await repo.get_by_class(class_id)
    else:
        # Default empty or select all within school (we filter results to current school)
        from sqlalchemy import select

        from app.modules.student_assignment.models import StudentAcademicAssignment

        stmt = (
            select(StudentAcademicAssignment)
            .where(StudentAcademicAssignment.school_id == current_user.school_id)
            .where(StudentAcademicAssignment.is_deleted == False)
        )
        execute_res = await db.execute(stmt)
        results = list(execute_res.scalars().all())

    # Ensure school boundary matches
    filtered = [r for r in results if r.school_id == current_user.school_id]

    return SuccessResponse[list[StudentAcademicAssignmentResponse]](
        message="Student academic assignments retrieved successfully.",
        data=[StudentAcademicAssignmentResponse.model_validate(r) for r in filtered],
    )


@router.get(
    "/{id}",
    response_model=SuccessResponse[StudentAcademicAssignmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get assignment details",
    description="Retrieves detail metadata for a single assignment.",
    responses={
        200: {"description": "Assignment profile resolved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.read' required."},
        404: {"description": "Assignment not found."},
    },
)
async def get_assignment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[StudentAcademicAssignmentResponse]:
    require_permission(current_user, "student.assignment.read")
    repo = StudentAcademicAssignmentRepository(db)

    assignment = await repo.get_by_id(id)
    if not assignment or assignment.school_id != current_user.school_id:
        from app.modules.student_assignment.exceptions import (
            AssignmentNotFoundException,
        )

        raise AssignmentNotFoundException()

    return SuccessResponse[StudentAcademicAssignmentResponse](
        message="Student assignment retrieved successfully.",
        data=StudentAcademicAssignmentResponse.model_validate(assignment),
    )


@router.put(
    "/{id}",
    response_model=UpdatedResponse[StudentAcademicAssignmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Update assignment parameters",
    description="Updates roll number, remarks, status, or left date of assignment.",
    responses={
        200: {"description": "Assignment updated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.update' required."},
        404: {"description": "Assignment not found."},
    },
)
async def update_assignment(
    id: uuid.UUID,
    body: StudentAcademicAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[StudentAcademicAssignmentResponse]:
    require_permission(current_user, "student.assignment.update")
    service = _make_service(db)

    assignment = await service.update_assignment(
        assignment_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(assignment)

    return UpdatedResponse[StudentAcademicAssignmentResponse](
        message="Student assignment updated successfully.",
        data=StudentAcademicAssignmentResponse.model_validate(assignment),
    )


@router.delete(
    "/{id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete student assignment",
    description="Soft-deletes an academic assignment.",
    responses={
        200: {"description": "Assignment soft-deleted successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.delete' required."},
        404: {"description": "Assignment not found."},
    },
)
async def delete_assignment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "student.assignment.delete")
    service = _make_service(db)

    await service.delete_assignment(
        assignment_id=id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return DeletedResponse(message="Student assignment soft-deleted successfully.")


@router.post(
    "/bulk",
    response_model=CreatedResponse[list[StudentAcademicAssignmentResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk assign students",
    description="Assigns multiple students to class section sequentially.",
    responses={
        201: {"description": "Bulk assignments completed successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.create' required."},
    },
)
async def bulk_assign(
    body: BulkAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[list[StudentAcademicAssignmentResponse]]:
    require_permission(current_user, "student.assignment.create")
    service = _make_service(db)

    assignments = await service.bulk_assign(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()

    return CreatedResponse[list[StudentAcademicAssignmentResponse]](
        message="Bulk student assignment completed successfully.",
        data=[StudentAcademicAssignmentResponse.model_validate(a) for a in assignments],
    )


@router.post(
    "/transfer",
    response_model=CreatedResponse[StudentAcademicAssignmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Transfer student",
    description="Closes active assignment and opens new one in target class/section.",
    responses={
        201: {"description": "Student transferred successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.assignment.transfer' required."},
        404: {"description": "Active assignment or student not found."},
    },
)
async def transfer_student(
    body: TransferAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentAcademicAssignmentResponse]:
    require_permission(current_user, "student.assignment.transfer")
    service = _make_service(db)

    assignment = await service.transfer_student(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(assignment)

    return CreatedResponse[StudentAcademicAssignmentResponse](
        message="Student transferred successfully.",
        data=StudentAcademicAssignmentResponse.model_validate(assignment),
    )
