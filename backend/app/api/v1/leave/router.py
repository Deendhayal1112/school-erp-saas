import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.leave.enums import (
    LeaveRequestStatus,
)
from app.modules.leave.exceptions import LeaveNotFoundException
from app.modules.leave.schemas import (
    HolidayCalendarCreate,
    HolidayCalendarResponse,
    LeaveBalanceResponse,
    LeavePolicyCreate,
    LeavePolicyResponse,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveTypeCreate,
    LeaveTypeResponse,
)
from app.modules.leave.service import LeaveService

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


def _make_service(db: AsyncSession) -> LeaveService:
    return LeaveService(db)


# --- 1. Leave Types ---
@router.post(
    "/types",
    response_model=CreatedResponse[LeaveTypeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Leave Type",
)
async def create_leave_type(
    body: LeaveTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[LeaveTypeResponse]:
    require_permission(current_user, "leave.manage")
    service = _make_service(db)
    lt = await service.create_leave_type(body, current_user.id, current_user.school_id)
    await db.commit()
    await db.refresh(lt)

    return CreatedResponse[LeaveTypeResponse](
        message="Leave type created successfully.",
        data=LeaveTypeResponse.model_validate(lt),
    )


@router.get(
    "/types",
    response_model=SuccessResponse[list[LeaveTypeResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Leave Types",
)
async def list_leave_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[LeaveTypeResponse]]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    items = await service.repo.list_leave_types(current_user.school_id)

    return SuccessResponse[list[LeaveTypeResponse]](
        message="Leave types retrieved successfully.",
        data=[LeaveTypeResponse.model_validate(x) for x in items],
    )


@router.get(
    "/types/{id}",
    response_model=SuccessResponse[LeaveTypeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Leave Type by ID",
)
async def get_leave_type(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[LeaveTypeResponse]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    lt = await service.repo.get_leave_type_by_id(id, current_user.school_id)
    if not lt:
        raise LeaveNotFoundException("Leave type not found")

    return SuccessResponse[LeaveTypeResponse](
        message="Leave type retrieved successfully.",
        data=LeaveTypeResponse.model_validate(lt),
    )


# --- 2. Leave Policies ---
@router.post(
    "/policies",
    response_model=CreatedResponse[LeavePolicyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Leave Policy",
)
async def create_leave_policy(
    body: LeavePolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[LeavePolicyResponse]:
    require_permission(current_user, "leave.manage")
    service = _make_service(db)
    lp = await service.create_leave_policy(
        body, current_user.id, current_user.school_id
    )
    await db.commit()
    await db.refresh(lp)

    return CreatedResponse[LeavePolicyResponse](
        message="Leave policy created successfully.",
        data=LeavePolicyResponse.model_validate(lp),
    )


@router.get(
    "/policies",
    response_model=SuccessResponse[list[LeavePolicyResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Leave Policies",
)
async def list_leave_policies(
    leave_type_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    designation_id: uuid.UUID | None = None,
    employee_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[LeavePolicyResponse]]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    items = await service.repo.list_leave_policies(
        school_id=current_user.school_id,
        leave_type_id=leave_type_id,
        department_id=department_id,
        designation_id=designation_id,
        employee_type=employee_type,
    )

    return SuccessResponse[list[LeavePolicyResponse]](
        message="Leave policies retrieved successfully.",
        data=[LeavePolicyResponse.model_validate(x) for x in items],
    )


# --- 3. Leave Balances ---
@router.get(
    "/balances/employee/{employee_id}",
    response_model=SuccessResponse[list[LeaveBalanceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get Leave Balances by Employee ID",
)
async def get_leave_balances(
    employee_id: uuid.UUID,
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[LeaveBalanceResponse]]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    target_year = year or date.today().year
    items = await service.repo.list_leave_balances(
        current_user.school_id, employee_id, target_year
    )

    return SuccessResponse[list[LeaveBalanceResponse]](
        message="Leave balances retrieved successfully.",
        data=[LeaveBalanceResponse.model_validate(x) for x in items],
    )


# --- 4. Leave Requests ---
@router.post(
    "/requests",
    response_model=CreatedResponse[LeaveRequestResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Apply for Leave Request",
)
async def apply_leave(
    body: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[LeaveRequestResponse]:
    require_permission(current_user, "leave.create")
    service = _make_service(db)
    lr = await service.apply_leave_request(
        employee_id=body.employee_id,
        leave_type_id=body.leave_type_id,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
        half_day=body.half_day,
        half_day_session=body.half_day_session,
        user_id=current_user.id,
        school_id=current_user.school_id,
    )
    await db.commit()
    await db.refresh(lr)

    return CreatedResponse[LeaveRequestResponse](
        message="Leave request applied successfully.",
        data=LeaveRequestResponse.model_validate(lr),
    )


@router.get(
    "/requests",
    response_model=SuccessResponse[list[LeaveRequestResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Leave Requests",
)
async def list_leave_requests(
    employee_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    status: LeaveRequestStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[LeaveRequestResponse]]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    offset = (page - 1) * limit
    items, total = await service.repo.list_leave_requests(
        school_id=current_user.school_id,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return SuccessResponse[list[LeaveRequestResponse]](
        message="Leave requests retrieved successfully.",
        data=[LeaveRequestResponse.model_validate(x) for x in items],
        pagination={"total": total, "page": page, "limit": limit},
    )


@router.get(
    "/requests/{id}",
    response_model=SuccessResponse[LeaveRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Leave Request Details",
)
async def get_leave_request(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[LeaveRequestResponse]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    lr = await service.repo.get_leave_request_by_id(id, current_user.school_id)
    if not lr:
        raise LeaveNotFoundException("Leave request not found")

    return SuccessResponse[LeaveRequestResponse](
        message="Leave request retrieved successfully.",
        data=LeaveRequestResponse.model_validate(lr),
    )


@router.patch(
    "/requests/{id}/approve",
    response_model=SuccessResponse[LeaveRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="Approve Leave Request",
)
async def approve_leave(
    id: uuid.UUID,
    remarks: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[LeaveRequestResponse]:
    require_permission(current_user, "leave.approve")
    service = _make_service(db)
    lr = await service.approve_leave_request(
        lr_id=id,
        remarks=remarks,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(lr)

    return SuccessResponse[LeaveRequestResponse](
        message="Leave request approved successfully.",
        data=LeaveRequestResponse.model_validate(lr),
    )


@router.patch(
    "/requests/{id}/reject",
    response_model=SuccessResponse[LeaveRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="Reject Leave Request",
)
async def reject_leave(
    id: uuid.UUID,
    remarks: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[LeaveRequestResponse]:
    require_permission(current_user, "leave.reject")
    service = _make_service(db)
    lr = await service.reject_leave_request(
        lr_id=id,
        remarks=remarks,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(lr)

    return SuccessResponse[LeaveRequestResponse](
        message="Leave request rejected successfully.",
        data=LeaveRequestResponse.model_validate(lr),
    )


@router.patch(
    "/requests/{id}/cancel",
    response_model=SuccessResponse[LeaveRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel Leave Request",
)
async def cancel_leave(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[LeaveRequestResponse]:
    require_permission(current_user, "leave.cancel")
    service = _make_service(db)
    lr = await service.cancel_leave_request(
        lr_id=id,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(lr)

    return SuccessResponse[LeaveRequestResponse](
        message="Leave request cancelled successfully.",
        data=LeaveRequestResponse.model_validate(lr),
    )


# --- 5. Holiday Calendar ---
@router.post(
    "/holidays",
    response_model=CreatedResponse[HolidayCalendarResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add School Holiday",
)
async def add_holiday(
    body: HolidayCalendarCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[HolidayCalendarResponse]:
    require_permission(current_user, "leave.manage")
    service = _make_service(db)
    hc = await service.create_holiday(body, current_user.id, current_user.school_id)
    await db.commit()
    await db.refresh(hc)

    return CreatedResponse[HolidayCalendarResponse](
        message="Holiday added successfully.",
        data=HolidayCalendarResponse.model_validate(hc),
    )


@router.get(
    "/holidays",
    response_model=SuccessResponse[list[HolidayCalendarResponse]],
    status_code=status.HTTP_200_OK,
    summary="List School Holidays",
)
async def list_holidays(
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[HolidayCalendarResponse]]:
    require_permission(current_user, "leave.read")
    service = _make_service(db)
    items = await service.repo.list_holidays(
        current_user.school_id, start_date=start_date, end_date=end_date
    )

    return SuccessResponse[list[HolidayCalendarResponse]](
        message="Holidays retrieved successfully.",
        data=[HolidayCalendarResponse.model_validate(x) for x in items],
    )
