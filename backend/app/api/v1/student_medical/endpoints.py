import uuid

from fastapi import APIRouter, Depends, status
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
from app.modules.student_medical.schemas import (
    AllergyCreate,
    AllergyResponse,
    StudentMedicalRecordCreate,
    StudentMedicalRecordResponse,
    StudentMedicalRecordUpdate,
    VaccinationCreate,
    VaccinationResponse,
)
from app.modules.student_medical.service import StudentMedicalService

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


def _make_service(db: AsyncSession) -> StudentMedicalService:
    return StudentMedicalService(db)


@router.post(
    "/{student_id}/medical",
    response_model=CreatedResponse[StudentMedicalRecordResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create student medical profile",
    description="Registers a new medical profile for the student and calculates BMI.",
    responses={
        201: {"description": "Medical record created successfully."},
        400: {
            "description": "Medical record already exists or vitals validation fails."
        },
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.create' required."},
        404: {"description": "Student not found."},
    },
)
async def create_medical_record(
    student_id: uuid.UUID,
    body: StudentMedicalRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[StudentMedicalRecordResponse]:
    require_permission(current_user, "student.medical.create")
    service = _make_service(db)

    record = await service.create_medical_record(
        student_id=student_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(record)

    return CreatedResponse[StudentMedicalRecordResponse](
        message="Student medical profile created successfully.",
        data=StudentMedicalRecordResponse.model_validate(record),
    )


@router.get(
    "/{student_id}/medical",
    response_model=SuccessResponse[StudentMedicalRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Get student medical profile details",
    description="Retrieves the active student medical profile including allergies and vaccinations.",
    responses={
        200: {"description": "Medical profile retrieved successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.read' required."},
        404: {"description": "Medical record or student not found."},
    },
)
async def get_medical_record(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[StudentMedicalRecordResponse]:
    require_permission(current_user, "student.medical.read")
    service = _make_service(db)

    record = await service.get_medical_record(
        student_id=student_id,
        school_id=current_user.school_id,
    )

    return SuccessResponse[StudentMedicalRecordResponse](
        message="Student medical profile retrieved successfully.",
        data=StudentMedicalRecordResponse.model_validate(record),
    )


@router.put(
    "/{student_id}/medical",
    response_model=UpdatedResponse[StudentMedicalRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Update student medical profile",
    description="Updates vitals or conditions on student medical profile and recalculates BMI.",
    responses={
        200: {"description": "Medical profile updated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.update' required."},
        404: {"description": "Medical record or student not found."},
    },
)
async def update_medical_record(
    student_id: uuid.UUID,
    body: StudentMedicalRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UpdatedResponse[StudentMedicalRecordResponse]:
    require_permission(current_user, "student.medical.update")
    service = _make_service(db)

    record = await service.update_medical_record(
        student_id=student_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(record)

    return UpdatedResponse[StudentMedicalRecordResponse](
        message="Student medical profile updated successfully.",
        data=StudentMedicalRecordResponse.model_validate(record),
    )


@router.delete(
    "/{student_id}/medical",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete student medical profile",
    description="Soft-deletes the medical profile associated with a student.",
    responses={
        200: {"description": "Medical record soft-deleted successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.delete' required."},
        404: {"description": "Medical record or student not found."},
    },
)
async def delete_medical_record(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "student.medical.delete")
    service = _make_service(db)

    await service.delete_medical_record(
        student_id=student_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return DeletedResponse(message="Student medical profile soft-deleted successfully.")


@router.post(
    "/{student_id}/medical/allergies",
    response_model=CreatedResponse[AllergyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register allergy entry",
    description="Maps a new allergy reactive profile to student medical history.",
    responses={
        201: {"description": "Allergy entry mapped successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.update' required."},
        404: {"description": "Medical profile or student not found."},
    },
)
async def add_allergy(
    student_id: uuid.UUID,
    body: AllergyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AllergyResponse]:
    require_permission(current_user, "student.medical.update")
    service = _make_service(db)

    allergy = await service.add_allergy(
        student_id=student_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(allergy)

    return CreatedResponse[AllergyResponse](
        message="Allergy reactive entry mapped successfully.",
        data=AllergyResponse.model_validate(allergy),
    )


@router.delete(
    "/{student_id}/medical/allergies/{allergy_id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove allergy entry",
    description="Deletes allergy record from student medical history.",
    responses={
        200: {"description": "Allergy record removed successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.update' required."},
        404: {"description": "Allergy or student not found."},
    },
)
async def remove_allergy(
    student_id: uuid.UUID,
    allergy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "student.medical.update")
    service = _make_service(db)

    await service.remove_allergy(
        student_id=student_id,
        allergy_id=allergy_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return DeletedResponse(message="Allergy record removed successfully.")


@router.post(
    "/{student_id}/medical/vaccinations",
    response_model=CreatedResponse[VaccinationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register vaccination entry",
    description="Maps a new vaccination record to student medical profile history.",
    responses={
        201: {"description": "Vaccination mapped successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.update' required."},
        404: {"description": "Medical profile or student not found."},
    },
)
async def add_vaccination(
    student_id: uuid.UUID,
    body: VaccinationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[VaccinationResponse]:
    require_permission(current_user, "student.medical.update")
    service = _make_service(db)

    vaccination = await service.add_vaccination(
        student_id=student_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
        data=body,
    )
    await db.commit()
    await db.refresh(vaccination)

    return CreatedResponse[VaccinationResponse](
        message="Vaccination record mapped successfully.",
        data=VaccinationResponse.model_validate(vaccination),
    )


@router.delete(
    "/{student_id}/medical/vaccinations/{vaccination_id}",
    response_model=DeletedResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove vaccination entry",
    description="Deletes vaccination record from student medical profile history.",
    responses={
        200: {"description": "Vaccination removed successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Permission 'student.medical.update' required."},
        404: {"description": "Vaccination or student not found."},
    },
)
async def remove_vaccination(
    student_id: uuid.UUID,
    vaccination_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DeletedResponse:
    require_permission(current_user, "student.medical.update")
    service = _make_service(db)

    await service.remove_vaccination(
        student_id=student_id,
        vaccination_id=vaccination_id,
        school_id=current_user.school_id,
        user_id=current_user.id,
    )
    await db.commit()

    return DeletedResponse(message="Vaccination record removed successfully.")
