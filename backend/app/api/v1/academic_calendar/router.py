import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.academic_calendar.schemas import (
    AcademicCalendarCreate,
    AcademicCalendarResponse,
    AcademicCalendarUpdate,
    GenerateCalendarRequest,
    HolidayCreate,
    HolidayResponse,
    HolidayUpdate,
    SpecialWorkingDayCreate,
    SpecialWorkingDayResponse,
    SpecialWorkingDayUpdate,
    WorkingDayCreate,
    WorkingDayResponse,
    WorkingDayUpdate,
)
from app.modules.academic_calendar.service import AcademicCalendarService

router = APIRouter(prefix="/academic-calendar", tags=["Academic Calendar"])


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
# WORKING DAYS ENDPOINTS
# ===========================================================================


@router.get(
    "/working-days",
    response_model=SuccessResponse[list[WorkingDayResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_working_days(
    academic_year_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[WorkingDayResponse]]:
    require_permission(current_user, "calendar.read")
    service = AcademicCalendarService(db)
    res = await service.get_working_days_by_year(current_user.school_id, academic_year_id)
    await db.commit()  # Might auto-seed default days
    return SuccessResponse[list[WorkingDayResponse]](data=res)


@router.post(
    "/working-days",
    response_model=CreatedResponse[WorkingDayResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_working_day(
    data: WorkingDayCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[WorkingDayResponse]:
    require_permission(current_user, "calendar.create")
    service = AcademicCalendarService(db)
    res = await service.create_working_day(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[WorkingDayResponse](data=res)


@router.put(
    "/working-days/{id}",
    response_model=SuccessResponse[WorkingDayResponse],
    status_code=status.HTTP_200_OK,
)
async def update_working_day(
    id: uuid.UUID,
    data: WorkingDayUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[WorkingDayResponse]:
    require_permission(current_user, "calendar.update")
    service = AcademicCalendarService(db)
    res = await service.update_working_day(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[WorkingDayResponse](data=res)


@router.delete(
    "/working-days/{id}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
async def delete_working_day(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, str]]:
    require_permission(current_user, "calendar.delete")
    service = AcademicCalendarService(db)
    await service.delete_working_day(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[dict[str, str]](data={"message": "Working day configuration deleted successfully."})


# ===========================================================================
# HOLIDAYS ENDPOINTS
# ===========================================================================


@router.get(
    "/holidays",
    response_model=SuccessResponse[list[HolidayResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_holidays(
    academic_year_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[HolidayResponse]]:
    require_permission(current_user, "calendar.read")
    service = AcademicCalendarService(db)
    res = await service.get_holidays_by_year(current_user.school_id, academic_year_id)
    return SuccessResponse[list[HolidayResponse]](data=res)


@router.post(
    "/holidays",
    response_model=CreatedResponse[HolidayResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_holiday(
    data: HolidayCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[HolidayResponse]:
    require_permission(current_user, "calendar.create")
    service = AcademicCalendarService(db)
    res = await service.create_holiday(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[HolidayResponse](data=res)


@router.put(
    "/holidays/{id}",
    response_model=SuccessResponse[HolidayResponse],
    status_code=status.HTTP_200_OK,
)
async def update_holiday(
    id: uuid.UUID,
    data: HolidayUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[HolidayResponse]:
    require_permission(current_user, "calendar.update")
    service = AcademicCalendarService(db)
    res = await service.update_holiday(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[HolidayResponse](data=res)


@router.delete(
    "/holidays/{id}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
async def delete_holiday(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, str]]:
    require_permission(current_user, "calendar.delete")
    service = AcademicCalendarService(db)
    await service.delete_holiday(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[dict[str, str]](data={"message": "Holiday configuration deleted successfully."})


# ===========================================================================
# SPECIAL WORKING DAYS ENDPOINTS
# ===========================================================================


@router.get(
    "/special-working-days",
    response_model=SuccessResponse[list[SpecialWorkingDayResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_special_working_days(
    academic_year_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[SpecialWorkingDayResponse]]:
    require_permission(current_user, "calendar.read")
    service = AcademicCalendarService(db)
    res = await service.get_special_working_days_by_year(current_user.school_id, academic_year_id)
    return SuccessResponse[list[SpecialWorkingDayResponse]](data=res)


@router.post(
    "/special-working-days",
    response_model=CreatedResponse[SpecialWorkingDayResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_special_working_day(
    data: SpecialWorkingDayCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[SpecialWorkingDayResponse]:
    require_permission(current_user, "calendar.create")
    service = AcademicCalendarService(db)
    res = await service.create_special_working_day(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[SpecialWorkingDayResponse](data=res)


@router.put(
    "/special-working-days/{id}",
    response_model=SuccessResponse[SpecialWorkingDayResponse],
    status_code=status.HTTP_200_OK,
)
async def update_special_working_day(
    id: uuid.UUID,
    data: SpecialWorkingDayUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[SpecialWorkingDayResponse]:
    require_permission(current_user, "calendar.update")
    service = AcademicCalendarService(db)
    res = await service.update_special_working_day(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[SpecialWorkingDayResponse](data=res)


@router.delete(
    "/special-working-days/{id}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
async def delete_special_working_day(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, str]]:
    require_permission(current_user, "calendar.delete")
    service = AcademicCalendarService(db)
    await service.delete_special_working_day(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[dict[str, str]](data={"message": "Special working day deleted successfully."})


# ===========================================================================
# ACADEMIC CALENDAR METADATA & BATCH GENERATION
# ===========================================================================


@router.get(
    "/entries",
    response_model=SuccessResponse[list[AcademicCalendarResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_calendar_entries(
    academic_year_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[AcademicCalendarResponse]]:
    require_permission(current_user, "calendar.read")
    service = AcademicCalendarService(db)
    res = await service.get_calendar_entries_by_year(current_user.school_id, academic_year_id)
    return SuccessResponse[list[AcademicCalendarResponse]](data=res)


@router.get(
    "/entries/month",
    response_model=SuccessResponse[list[AcademicCalendarResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_calendar_entries_by_month(
    academic_year_id: uuid.UUID = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[AcademicCalendarResponse]]:
    require_permission(current_user, "calendar.read")
    service = AcademicCalendarService(db)
    res = await service.get_calendar_entries_by_month(current_user.school_id, academic_year_id, year, month)
    return SuccessResponse[list[AcademicCalendarResponse]](data=res)


@router.post(
    "/entries",
    response_model=CreatedResponse[AcademicCalendarResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_calendar_entry(
    data: AcademicCalendarCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CreatedResponse[AcademicCalendarResponse]:
    require_permission(current_user, "calendar.create")
    service = AcademicCalendarService(db)
    res = await service.create_calendar_entry(current_user.school_id, data, current_user)
    await db.commit()
    return CreatedResponse[AcademicCalendarResponse](data=res)


@router.put(
    "/entries/{id}",
    response_model=SuccessResponse[AcademicCalendarResponse],
    status_code=status.HTTP_200_OK,
)
async def update_calendar_entry(
    id: uuid.UUID,
    data: AcademicCalendarUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[AcademicCalendarResponse]:
    require_permission(current_user, "calendar.update")
    service = AcademicCalendarService(db)
    res = await service.update_calendar_entry(id, current_user.school_id, data, current_user)
    await db.commit()
    return SuccessResponse[AcademicCalendarResponse](data=res)


@router.delete(
    "/entries/{id}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
async def delete_calendar_entry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, str]]:
    require_permission(current_user, "calendar.delete")
    service = AcademicCalendarService(db)
    await service.delete_calendar_entry(id, current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[dict[str, str]](data={"message": "Calendar event deleted successfully."})


@router.post(
    "/generate",
    response_model=SuccessResponse[dict[str, int]],
    status_code=status.HTTP_200_OK,
)
async def generate_calendar(
    data: GenerateCalendarRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, int]]:
    require_permission(current_user, "calendar.create")
    service = AcademicCalendarService(db)
    count = await service.generate_calendar(current_user.school_id, data.academic_year_id, current_user)
    await db.commit()
    return SuccessResponse[dict[str, int]](data={"generated_days": count})


@router.get(
    "/calculate-working-days",
    response_model=SuccessResponse[dict[str, int]],
    status_code=status.HTTP_200_OK,
)
async def calculate_working_days(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, int]]:
    require_permission(current_user, "calendar.read")
    service = AcademicCalendarService(db)
    count = await service.calculate_working_days(current_user.school_id, start_date, end_date)
    return SuccessResponse[dict[str, int]](data={"working_days": count})
