import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import (
    CreatedResponse,
    SuccessResponse,
)
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.student_progression.schemas import (
    AlumniConversionRequest,
    BulkPromotionRequest,
    StudentGraduationRequest,
    StudentProgressionResponse,
    StudentPromotionRequest,
    StudentTransferRequest,
)
from app.modules.student_progression.service import StudentProgressionService

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


def _make_service(db: AsyncSession) -> StudentProgressionService:
    return StudentProgressionService(db)


@router.post(
    "/promote",
    response_model=CreatedResponse[StudentProgressionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Promote student",
    description="Promotes a student to target academic class section.",
    responses={
        201: {"description": "Student promoted successfully."},
        400: {"description": "Invalid promotion sequence or roll number conflict."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.progression.promote' required."},
        404: {"description": "Student not found."},
    },
)
async def promote_student(
    body: StudentPromotionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentProgressionResponse]:
    require_permission(current_user, "student.progression.promote")
    service = _make_service(db)

    progression = await service.promote_student(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(progression)

    return CreatedResponse[StudentProgressionResponse](
        message="Student promoted successfully.",
        data=StudentProgressionResponse.model_validate(progression),
    )


@router.post(
    "/bulk-promote",
    response_model=CreatedResponse[list[StudentProgressionResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk promote students",
    description="Bulk promotes multiple students to target next academic year class section context.",
    responses={
        201: {"description": "Bulk promotions completed successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.progression.promote' required."},
    },
)
async def bulk_promote(
    body: BulkPromotionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[list[StudentProgressionResponse]]:
    require_permission(current_user, "student.progression.promote")
    service = _make_service(db)

    progressions = await service.bulk_promote(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()

    return CreatedResponse[list[StudentProgressionResponse]](
        message="Bulk promotion processed successfully.",
        data=[StudentProgressionResponse.model_validate(p) for p in progressions],
    )


@router.post(
    "/transfer",
    response_model=CreatedResponse[StudentProgressionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Transfer student",
    description="Logs student class transfer progression actions.",
    responses={
        201: {"description": "Student transferred successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.progression.transfer' required."},
        404: {"description": "Active assignment or student not found."},
    },
)
async def transfer_student(
    body: StudentTransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentProgressionResponse]:
    require_permission(current_user, "student.progression.transfer")
    service = _make_service(db)

    progression = await service.transfer_student(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(progression)

    return CreatedResponse[StudentProgressionResponse](
        message="Student transfer log created successfully.",
        data=StudentProgressionResponse.model_validate(progression),
    )


@router.post(
    "/graduate",
    response_model=CreatedResponse[StudentProgressionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Graduate student",
    description="Completes student graduation progression pipeline checks.",
    responses={
        201: {"description": "Student graduated successfully."},
        400: {"description": "Not final class context violation."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.progression.graduate' required."},
        404: {"description": "Active assignment or student not found."},
    },
)
async def graduate_student(
    body: StudentGraduationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentProgressionResponse]:
    require_permission(current_user, "student.progression.graduate")
    service = _make_service(db)

    progression = await service.graduate_student(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(progression)

    return CreatedResponse[StudentProgressionResponse](
        message="Student graduated successfully.",
        data=StudentProgressionResponse.model_validate(progression),
    )


@router.post(
    "/alumni",
    response_model=CreatedResponse[StudentProgressionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Convert to alumni",
    description="Converts active student registration profile to alumni status.",
    responses={
        201: {"description": "Student alumni conversion completed successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.progression.alumni' required."},
        404: {"description": "Active assignment or student not found."},
    },
)
async def convert_to_alumni(
    body: AlumniConversionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentProgressionResponse]:
    require_permission(current_user, "student.progression.alumni")
    service = _make_service(db)

    progression = await service.convert_to_alumni(
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(progression)

    return CreatedResponse[StudentProgressionResponse](
        message="Student converted to alumni successfully.",
        data=StudentProgressionResponse.model_validate(progression),
    )


@router.get(
    "/history/{student_id}",
    response_model=SuccessResponse[list[StudentProgressionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get student progression history",
    description="Retrieves list of all progression events logging student promotions and transfers.",
    responses={
        200: {"description": "Progression history resolved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.progression.read' required."},
        404: {"description": "Student not found."},
    },
)
async def get_progression_history(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[StudentProgressionResponse]]:
    require_permission(current_user, "student.progression.read")
    service = _make_service(db)

    results = await service.get_progression_history(
        student_id=student_id,
        school_id=current_user.school_id,
    )

    return SuccessResponse[list[StudentProgressionResponse]](
        message="Student progression history resolved successfully.",
        data=[StudentProgressionResponse.model_validate(r) for r in results],
    )
