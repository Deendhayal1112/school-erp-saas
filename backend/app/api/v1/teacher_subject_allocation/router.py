import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.teacher_subject_allocation.schemas import (
    SubjectQualificationCreate,
    SubjectQualificationResponse,
    SubjectQualificationUpdate,
    TeacherAssignmentSummaryResponse,
    TeacherSubjectAllocationCreate,
    TeacherSubjectAllocationResponse,
    TeacherSubjectAllocationUpdate,
    TeacherWorkloadCreate,
    TeacherWorkloadResponse,
    TeacherWorkloadUpdate,
)
from app.modules.teacher_subject_allocation.service import TeacherSubjectAllocationService

router = APIRouter(tags=["Teacher Subject Allocation"])


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


# ===========================================================================
# ALLOCATIONS ENDPOINTS
# ===========================================================================


@router.post(
    "/allocations",
    response_model=CreatedResponse[TeacherSubjectAllocationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_allocation(
    data: TeacherSubjectAllocationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[TeacherSubjectAllocationResponse]:
    require_permission(current_user, "teacher_subject.create")
    service = TeacherSubjectAllocationService(db)
    res = await service.allocate_subject(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[TeacherSubjectAllocationResponse](data=res)


@router.get(
    "/allocations",
    response_model=SuccessResponse[list[TeacherSubjectAllocationResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_allocations(
    teacher_id: uuid.UUID | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    academic_year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("teacher_name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[TeacherSubjectAllocationResponse]]:
    require_permission(current_user, "teacher_subject.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.list_allocations(
        school_id=current_user.school_id,
        teacher_id=teacher_id,
        department_id=department_id,
        subject_id=subject_id,
        class_id=class_id,
        section_id=section_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        status=status,
        is_active=is_active,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[TeacherSubjectAllocationResponse]](data=list(res))


@router.get(
    "/allocations/{id}",
    response_model=SuccessResponse[TeacherSubjectAllocationResponse],
    status_code=status.HTTP_200_OK,
)
async def get_allocation(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherSubjectAllocationResponse]:
    require_permission(current_user, "teacher_subject.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.get_allocation(id, current_user.school_id)
    return SuccessResponse[TeacherSubjectAllocationResponse](data=res)


@router.put(
    "/allocations/{id}",
    response_model=SuccessResponse[TeacherSubjectAllocationResponse],
    status_code=status.HTTP_200_OK,
)
async def update_allocation(
    id: uuid.UUID,
    data: TeacherSubjectAllocationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherSubjectAllocationResponse]:
    require_permission(current_user, "teacher_subject.update")
    service = TeacherSubjectAllocationService(db)
    res = await service.update_allocation(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[TeacherSubjectAllocationResponse](data=res)


@router.delete(
    "/allocations/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_allocation(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "teacher_subject.delete")
    service = TeacherSubjectAllocationService(db)
    await service.remove_allocation(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Allocation removed successfully.")


# ===========================================================================
# WORKLOADS ENDPOINTS
# ===========================================================================


@router.post(
    "/workloads",
    response_model=CreatedResponse[TeacherWorkloadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_workload(
    data: TeacherWorkloadCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[TeacherWorkloadResponse]:
    require_permission(current_user, "teacher_subject.update")
    service = TeacherSubjectAllocationService(db)
    res = await service.create_workload(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[TeacherWorkloadResponse](data=res)


@router.get(
    "/workloads",
    response_model=SuccessResponse[list[TeacherWorkloadResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_workloads(
    teacher_id: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[TeacherWorkloadResponse]]:
    require_permission(current_user, "teacher_workload.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.list_workloads(
        school_id=current_user.school_id,
        teacher_id=teacher_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[TeacherWorkloadResponse]](data=list(res))


@router.get(
    "/workloads/{id}",
    response_model=SuccessResponse[TeacherWorkloadResponse],
    status_code=status.HTTP_200_OK,
)
async def get_workload(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherWorkloadResponse]:
    require_permission(current_user, "teacher_workload.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.get_workload(id, current_user.school_id)
    return SuccessResponse[TeacherWorkloadResponse](data=res)


@router.put(
    "/workloads/{id}",
    response_model=SuccessResponse[TeacherWorkloadResponse],
    status_code=status.HTTP_200_OK,
)
async def update_workload(
    id: uuid.UUID,
    data: TeacherWorkloadUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherWorkloadResponse]:
    require_permission(current_user, "teacher_subject.update")
    service = TeacherSubjectAllocationService(db)
    res = await service.update_workload(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[TeacherWorkloadResponse](data=res)


# ===========================================================================
# QUALIFICATIONS ENDPOINTS
# ===========================================================================


@router.post(
    "/qualifications",
    response_model=CreatedResponse[SubjectQualificationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_qualification(
    data: SubjectQualificationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[SubjectQualificationResponse]:
    require_permission(current_user, "teacher_subject.create")
    service = TeacherSubjectAllocationService(db)
    res = await service.create_qualification(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[SubjectQualificationResponse](data=res)


@router.get(
    "/qualifications",
    response_model=SuccessResponse[list[SubjectQualificationResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_qualifications(
    teacher_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    qualification_level: str | None = Query(None),
    certified: bool | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[SubjectQualificationResponse]]:
    require_permission(current_user, "teacher_subject.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.list_qualifications(
        school_id=current_user.school_id,
        teacher_id=teacher_id,
        subject_id=subject_id,
        qualification_level=qualification_level,
        certified=certified,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[SubjectQualificationResponse]](data=list(res))


@router.get(
    "/qualifications/{id}",
    response_model=SuccessResponse[SubjectQualificationResponse],
    status_code=status.HTTP_200_OK,
)
async def get_qualification(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[SubjectQualificationResponse]:
    require_permission(current_user, "teacher_subject.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.get_qualification(id, current_user.school_id)
    return SuccessResponse[SubjectQualificationResponse](data=res)


@router.put(
    "/qualifications/{id}",
    response_model=SuccessResponse[SubjectQualificationResponse],
    status_code=status.HTTP_200_OK,
)
async def update_qualification(
    id: uuid.UUID,
    data: SubjectQualificationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[SubjectQualificationResponse]:
    require_permission(current_user, "teacher_subject.update")
    service = TeacherSubjectAllocationService(db)
    res = await service.update_qualification(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[SubjectQualificationResponse](data=res)


@router.delete(
    "/qualifications/{id}",
    response_model=SuccessResponse[str],
    status_code=status.HTTP_200_OK,
)
async def delete_qualification(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[str]:
    require_permission(current_user, "teacher_subject.delete")
    service = TeacherSubjectAllocationService(db)
    await service.delete_qualification(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[str](data="Subject qualification deleted successfully.")


# ===========================================================================
# SUMMARY ENDPOINTS
# ===========================================================================


@router.get(
    "/teachers/{id}/summary",
    response_model=SuccessResponse[TeacherAssignmentSummaryResponse],
    status_code=status.HTTP_200_OK,
)
async def get_teacher_summary(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TeacherAssignmentSummaryResponse]:
    require_permission(current_user, "teacher_subject.read")
    service = TeacherSubjectAllocationService(db)
    res = await service.generate_teacher_assignment_summary(id, current_user.school_id)
    return SuccessResponse[TeacherAssignmentSummaryResponse](data=res)
