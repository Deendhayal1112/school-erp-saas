import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.timetable_generator.schemas import (
    GenerateTimetableRequest,
    GenerateTimetableResponse,
    GenerationJobResponse,
    GenerationResultResponse,
    ValidationRequest,
    ValidationResponse,
)
from app.modules.timetable_generator.service import TimetableGeneratorService

router = APIRouter(tags=["Timetable Generator"])


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


@router.post(
    "/generate",
    response_model=CreatedResponse[GenerateTimetableResponse],
    status_code=status.HTTP_201_CREATED,
)
async def trigger_generation(
    data: GenerateTimetableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[GenerateTimetableResponse]:
    require_permission(current_user, "timetable.generate")
    service = TimetableGeneratorService(db)
    res = await service.trigger_generation(current_user.school_id, data, current_user)
    resp_data = GenerateTimetableResponse(
        job_id=res.id,
        status=res.status,
        job_name=res.job_name,
        message="Automatic timetable generation started in background.",
    )
    return CreatedResponse[GenerateTimetableResponse](data=resp_data)


@router.get(
    "/jobs",
    response_model=SuccessResponse[list[GenerationJobResponse]],
)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[GenerationJobResponse]]:
    require_permission(current_user, "timetable.read")
    service = TimetableGeneratorService(db)
    jobs = await service.repo.list_jobs(current_user.school_id, skip, limit)
    resp_data = [GenerationJobResponse.model_validate(item) for item in jobs]
    return SuccessResponse[list[GenerationJobResponse]](data=resp_data)


@router.get(
    "/jobs/{id}",
    response_model=SuccessResponse[GenerationJobResponse],
)
async def get_job(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[GenerationJobResponse]:
    require_permission(current_user, "timetable.read")
    service = TimetableGeneratorService(db)
    job = await service.get_job(id, current_user.school_id)
    resp_data = GenerationJobResponse.model_validate(job)
    return SuccessResponse[GenerationJobResponse](data=resp_data)


@router.get(
    "/results/{id}",
    response_model=SuccessResponse[GenerationResultResponse],
)
async def get_result(
    id: uuid.UUID,  # job id representing the generator task job run
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[GenerationResultResponse]:
    require_permission(current_user, "timetable.read")
    service = TimetableGeneratorService(db)
    res = await service.get_result(id, current_user.school_id)
    resp_data = GenerationResultResponse.model_validate(res)
    return SuccessResponse[GenerationResultResponse](data=resp_data)


@router.post(
    "/validate",
    response_model=SuccessResponse[ValidationResponse],
)
async def validate_setup(
    data: ValidationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ValidationResponse]:
    require_permission(current_user, "timetable.validate")
    service = TimetableGeneratorService(db)
    res = await service.validate_timetable_setup(current_user.school_id, data)
    return SuccessResponse[ValidationResponse](data=res)
