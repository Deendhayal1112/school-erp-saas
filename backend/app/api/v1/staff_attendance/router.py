"""
Staff Attendance REST API Router — aligned with project router conventions.

Endpoints:
  Shifts         GET/POST /attendance/shifts, GET/PATCH/DELETE /attendance/shifts/{id}
  Policies       GET/POST /attendance/policies, GET/PATCH /attendance/policies/{id}
  Records        GET/POST /attendance/records, GET/PATCH /attendance/records/{id}
                 GET /attendance/records/summary/{employee_id}
  Regularize     GET/POST /attendance/regularizations
                 PATCH /attendance/regularizations/{id}/approve|reject
  Devices        GET/POST /attendance/devices, GET/PATCH /attendance/devices/{id}
  Logs           GET/POST /attendance/logs
                 POST /attendance/logs/process
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import CreatedResponse, SuccessResponse
from app.db.database import get_db
from app.dependencies.current_user import get_current_active_user
from app.exceptions.exceptions import ForbiddenException
from app.models.user import User
from app.modules.staff_attendance.enums import (
    AttendanceStatus,
    DeviceStatus,
    RegularizationStatus,
)
from app.modules.staff_attendance.schemas import (
    AttendanceDeviceCreate,
    AttendanceDeviceResponse,
    AttendanceDeviceUpdate,
    AttendanceLogCreate,
    AttendanceLogResponse,
    AttendancePolicyCreate,
    AttendancePolicyResponse,
    AttendancePolicyUpdate,
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceShiftCreate,
    AttendanceShiftResponse,
    AttendanceShiftUpdate,
    AttendanceSummary,
    RegularizationApproveReject,
    RegularizationCreate,
    RegularizationResponse,
)
from app.modules.staff_attendance.service import AttendanceService

router = APIRouter()


# ---------------------------------------------------------------------------
# Inline RBAC helper (same pattern as leave router)
# ---------------------------------------------------------------------------


def require_permission(user: User, code: str) -> None:
    """Enforces RBAC permission check on the active user context."""
    permission_codes = {
        rp.permission.code
        for rp in user.role.role_permissions
        if rp.permission is not None
    }
    if code not in permission_codes:
        raise ForbiddenException(f"Insufficient permissions. Required: '{code}'.")


def _make_service(db: AsyncSession) -> AttendanceService:
    return AttendanceService(db)


# ===========================================================================
# SHIFTS
# ===========================================================================


@router.post(
    "/shifts",
    response_model=CreatedResponse[AttendanceShiftResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an attendance shift",
)
async def create_shift(
    body: AttendanceShiftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AttendanceShiftResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    shift = await service.create_shift(current_user.school_id, body, current_user)
    await db.commit()
    await db.refresh(shift)
    return CreatedResponse[AttendanceShiftResponse](
        message="Shift created successfully.",
        data=AttendanceShiftResponse.model_validate(shift),
    )


@router.get(
    "/shifts",
    response_model=SuccessResponse[list[AttendanceShiftResponse]],
    status_code=status.HTTP_200_OK,
    summary="List attendance shifts",
)
async def list_shifts(
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AttendanceShiftResponse]]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    shifts = await service.list_shifts(current_user.school_id, active_only)
    return SuccessResponse[list[AttendanceShiftResponse]](
        message="Shifts retrieved successfully.",
        data=[AttendanceShiftResponse.model_validate(s) for s in shifts],
    )


@router.get(
    "/shifts/{shift_id}",
    response_model=SuccessResponse[AttendanceShiftResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a shift by ID",
)
async def get_shift(
    shift_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceShiftResponse]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    shift = await service.get_shift(shift_id, current_user.school_id)
    return SuccessResponse[AttendanceShiftResponse](
        message="Shift retrieved successfully.",
        data=AttendanceShiftResponse.model_validate(shift),
    )


@router.patch(
    "/shifts/{shift_id}",
    response_model=SuccessResponse[AttendanceShiftResponse],
    status_code=status.HTTP_200_OK,
    summary="Update a shift",
)
async def update_shift(
    shift_id: uuid.UUID,
    body: AttendanceShiftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceShiftResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    shift = await service.update_shift(shift_id, current_user.school_id, body, current_user)
    await db.commit()
    await db.refresh(shift)
    return SuccessResponse[AttendanceShiftResponse](
        message="Shift updated successfully.",
        data=AttendanceShiftResponse.model_validate(shift),
    )


@router.delete(
    "/shifts/{shift_id}",
    response_model=SuccessResponse[AttendanceShiftResponse],
    status_code=status.HTTP_200_OK,
    summary="Archive a shift",
)
async def archive_shift(
    shift_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceShiftResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    shift = await service.archive_shift(shift_id, current_user.school_id, current_user)
    await db.commit()
    await db.refresh(shift)
    return SuccessResponse[AttendanceShiftResponse](
        message="Shift archived successfully.",
        data=AttendanceShiftResponse.model_validate(shift),
    )


# ===========================================================================
# POLICIES
# ===========================================================================


@router.post(
    "/policies",
    response_model=CreatedResponse[AttendancePolicyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an attendance policy",
)
async def create_policy(
    body: AttendancePolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AttendancePolicyResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    policy = await service.create_policy(current_user.school_id, body, current_user)
    await db.commit()
    await db.refresh(policy)
    return CreatedResponse[AttendancePolicyResponse](
        message="Policy created successfully.",
        data=AttendancePolicyResponse.model_validate(policy),
    )


@router.get(
    "/policies",
    response_model=SuccessResponse[list[AttendancePolicyResponse]],
    status_code=status.HTTP_200_OK,
    summary="List attendance policies",
)
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AttendancePolicyResponse]]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    policies = await service.list_policies(current_user.school_id)
    return SuccessResponse[list[AttendancePolicyResponse]](
        message="Policies retrieved successfully.",
        data=[AttendancePolicyResponse.model_validate(p) for p in policies],
    )


@router.get(
    "/policies/{policy_id}",
    response_model=SuccessResponse[AttendancePolicyResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a policy by ID",
)
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendancePolicyResponse]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    policy = await service.get_policy(policy_id, current_user.school_id)
    return SuccessResponse[AttendancePolicyResponse](
        message="Policy retrieved successfully.",
        data=AttendancePolicyResponse.model_validate(policy),
    )


@router.patch(
    "/policies/{policy_id}",
    response_model=SuccessResponse[AttendancePolicyResponse],
    status_code=status.HTTP_200_OK,
    summary="Update an attendance policy",
)
async def update_policy(
    policy_id: uuid.UUID,
    body: AttendancePolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendancePolicyResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    policy = await service.update_policy(
        policy_id, current_user.school_id, body, current_user
    )
    await db.commit()
    await db.refresh(policy)
    return SuccessResponse[AttendancePolicyResponse](
        message="Policy updated successfully.",
        data=AttendancePolicyResponse.model_validate(policy),
    )


# ===========================================================================
# RECORDS
# ===========================================================================


@router.post(
    "/records",
    response_model=CreatedResponse[AttendanceRecordResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Mark attendance for an employee",
)
async def mark_attendance(
    body: AttendanceRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AttendanceRecordResponse]:
    require_permission(current_user, "attendance.create")
    service = _make_service(db)
    record = await service.mark_attendance(current_user.school_id, body, current_user)
    await db.commit()
    await db.refresh(record)
    return CreatedResponse[AttendanceRecordResponse](
        message="Attendance marked successfully.",
        data=AttendanceRecordResponse.model_validate(record),
    )


@router.get(
    "/records/summary/{employee_id}",
    response_model=SuccessResponse[AttendanceSummary],
    status_code=status.HTTP_200_OK,
    summary="Monthly attendance summary for an employee",
)
async def get_attendance_summary(
    employee_id: uuid.UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceSummary]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    summary = await service.get_attendance_summary(
        current_user.school_id, employee_id, month, year
    )
    return SuccessResponse[AttendanceSummary](
        message="Attendance summary retrieved successfully.",
        data=summary,
    )


@router.get(
    "/records",
    response_model=SuccessResponse[list[AttendanceRecordResponse]],
    status_code=status.HTTP_200_OK,
    summary="List attendance records with filters",
)
async def list_records(
    employee_id: uuid.UUID | None = Query(None),
    shift_id: uuid.UUID | None = Query(None),
    status_filter: AttendanceStatus | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AttendanceRecordResponse]]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    records = await service.list_records(
        school_id=current_user.school_id,
        employee_id=employee_id,
        shift_id=shift_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return SuccessResponse[list[AttendanceRecordResponse]](
        message="Attendance records retrieved successfully.",
        data=[AttendanceRecordResponse.model_validate(r) for r in records],
    )


@router.get(
    "/records/{record_id}",
    response_model=SuccessResponse[AttendanceRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Get an attendance record by ID",
)
async def get_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceRecordResponse]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    record = await service.get_record(record_id, current_user.school_id)
    return SuccessResponse[AttendanceRecordResponse](
        message="Record retrieved successfully.",
        data=AttendanceRecordResponse.model_validate(record),
    )


@router.patch(
    "/records/{record_id}",
    response_model=SuccessResponse[AttendanceRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Update an attendance record",
)
async def update_record(
    record_id: uuid.UUID,
    body: AttendanceRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceRecordResponse]:
    require_permission(current_user, "attendance.update")
    service = _make_service(db)
    record = await service.update_record(
        record_id, current_user.school_id, body, current_user
    )
    await db.commit()
    await db.refresh(record)
    return SuccessResponse[AttendanceRecordResponse](
        message="Attendance record updated successfully.",
        data=AttendanceRecordResponse.model_validate(record),
    )


# ===========================================================================
# REGULARIZATION
# ===========================================================================


@router.post(
    "/regularizations",
    response_model=CreatedResponse[RegularizationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Submit an attendance regularization request",
)
async def submit_regularization(
    body: RegularizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[RegularizationResponse]:
    require_permission(current_user, "attendance.regularize")
    
    from sqlalchemy import select
    from app.modules.employee.models import Employee
    
    stmt = select(Employee.id).where(
        Employee.email == current_user.email,
        Employee.school_id == current_user.school_id,
        Employee.is_deleted == False,
    )
    res = await db.execute(stmt)
    employee_id = res.scalar_one_or_none()
    if not employee_id:
        raise ForbiddenException("User does not have an active employee profile.")
        
    service = _make_service(db)
    reg = await service.submit_regularization(
        school_id=current_user.school_id,
        employee_id=employee_id,
        data=body,
        actor=current_user,
    )
    await db.commit()
    await db.refresh(reg)
    return CreatedResponse[RegularizationResponse](
        message="Regularization submitted successfully.",
        data=RegularizationResponse.model_validate(reg),
    )


@router.get(
    "/regularizations",
    response_model=SuccessResponse[list[RegularizationResponse]],
    status_code=status.HTTP_200_OK,
    summary="List regularization requests",
)
async def list_regularizations(
    employee_id: uuid.UUID | None = Query(None),
    reg_status: RegularizationStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[RegularizationResponse]]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    regs = await service.list_regularizations(
        current_user.school_id, employee_id, reg_status, skip, limit
    )
    return SuccessResponse[list[RegularizationResponse]](
        message="Regularizations retrieved successfully.",
        data=[RegularizationResponse.model_validate(r) for r in regs],
    )


@router.patch(
    "/regularizations/{reg_id}/approve",
    response_model=SuccessResponse[RegularizationResponse],
    status_code=status.HTTP_200_OK,
    summary="Approve a regularization request",
)
async def approve_regularization(
    reg_id: uuid.UUID,
    body: RegularizationApproveReject,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[RegularizationResponse]:
    require_permission(current_user, "attendance.approve")
    service = _make_service(db)
    reg = await service.approve_regularization(
        reg_id, current_user.school_id, body, current_user
    )
    await db.commit()
    await db.refresh(reg)
    return SuccessResponse[RegularizationResponse](
        message="Regularization approved successfully.",
        data=RegularizationResponse.model_validate(reg),
    )


@router.patch(
    "/regularizations/{reg_id}/reject",
    response_model=SuccessResponse[RegularizationResponse],
    status_code=status.HTTP_200_OK,
    summary="Reject a regularization request",
)
async def reject_regularization(
    reg_id: uuid.UUID,
    body: RegularizationApproveReject,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[RegularizationResponse]:
    require_permission(current_user, "attendance.approve")
    service = _make_service(db)
    reg = await service.reject_regularization(
        reg_id, current_user.school_id, body, current_user
    )
    await db.commit()
    await db.refresh(reg)
    return SuccessResponse[RegularizationResponse](
        message="Regularization rejected successfully.",
        data=RegularizationResponse.model_validate(reg),
    )


# ===========================================================================
# DEVICES
# ===========================================================================


@router.post(
    "/devices",
    response_model=CreatedResponse[AttendanceDeviceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register an attendance device",
)
async def create_device(
    body: AttendanceDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AttendanceDeviceResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    device = await service.create_device(current_user.school_id, body, current_user)
    await db.commit()
    await db.refresh(device)
    return CreatedResponse[AttendanceDeviceResponse](
        message="Device registered successfully.",
        data=AttendanceDeviceResponse.model_validate(device),
    )


@router.get(
    "/devices",
    response_model=SuccessResponse[list[AttendanceDeviceResponse]],
    status_code=status.HTTP_200_OK,
    summary="List registered attendance devices",
)
async def list_devices(
    dev_status: DeviceStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AttendanceDeviceResponse]]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    devices = await service.list_devices(current_user.school_id, dev_status)
    return SuccessResponse[list[AttendanceDeviceResponse]](
        message="Devices retrieved successfully.",
        data=[AttendanceDeviceResponse.model_validate(d) for d in devices],
    )


@router.get(
    "/devices/{device_id}",
    response_model=SuccessResponse[AttendanceDeviceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a device by ID",
)
async def get_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceDeviceResponse]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    device = await service.get_device(device_id, current_user.school_id)
    return SuccessResponse[AttendanceDeviceResponse](
        message="Device retrieved successfully.",
        data=AttendanceDeviceResponse.model_validate(device),
    )


@router.patch(
    "/devices/{device_id}",
    response_model=SuccessResponse[AttendanceDeviceResponse],
    status_code=status.HTTP_200_OK,
    summary="Update an attendance device",
)
async def update_device(
    device_id: uuid.UUID,
    body: AttendanceDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AttendanceDeviceResponse]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    device = await service.update_device(
        device_id, current_user.school_id, body, current_user
    )
    await db.commit()
    await db.refresh(device)
    return SuccessResponse[AttendanceDeviceResponse](
        message="Device updated successfully.",
        data=AttendanceDeviceResponse.model_validate(device),
    )


# ===========================================================================
# LOGS
# ===========================================================================


@router.post(
    "/logs",
    response_model=CreatedResponse[AttendanceLogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a raw attendance log entry",
)
async def create_log(
    body: AttendanceLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CreatedResponse[AttendanceLogResponse]:
    require_permission(current_user, "attendance.create")
    service = _make_service(db)
    log = await service.create_log(current_user.school_id, body, current_user)
    await db.commit()
    await db.refresh(log)
    return CreatedResponse[AttendanceLogResponse](
        message="Attendance log created successfully.",
        data=AttendanceLogResponse.model_validate(log),
    )


@router.get(
    "/logs",
    response_model=SuccessResponse[list[AttendanceLogResponse]],
    status_code=status.HTTP_200_OK,
    summary="List attendance logs",
)
async def list_logs(
    employee_id: uuid.UUID | None = Query(None),
    device_id: uuid.UUID | None = Query(None),
    is_processed: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AttendanceLogResponse]]:
    require_permission(current_user, "attendance.read")
    service = _make_service(db)
    logs = await service.list_logs(
        current_user.school_id, employee_id, device_id, is_processed, skip, limit
    )
    return SuccessResponse[list[AttendanceLogResponse]](
        message="Logs retrieved successfully.",
        data=[AttendanceLogResponse.model_validate(lg) for lg in logs],
    )


@router.post(
    "/logs/process",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Process unprocessed biometric logs into attendance records",
)
async def process_biometric_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[dict]:
    require_permission(current_user, "attendance.manage")
    service = _make_service(db)
    count = await service.process_biometric_logs(current_user.school_id, current_user)
    await db.commit()
    return SuccessResponse[dict](
        message=f"{count} attendance log(s) processed successfully.",
        data={"processed_count": count},
    )
