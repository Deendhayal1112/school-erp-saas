import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.leave.enums import (
    ApprovalStatus,
    GenderRestriction,
    HalfDaySession,
    HolidayType,
    LeaveRequestStatus,
    LeaveStatus,
)


# Leave Type Schemas
class LeaveTypeCreate(BaseModel):
    leave_code: str = Field(..., min_length=2, max_length=50)
    leave_name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    annual_quota: int = Field(0, ge=0)
    carry_forward: bool = False
    maximum_carry_forward: int = Field(0, ge=0)
    encashment_allowed: bool = False
    requires_attachment: bool = False
    requires_approval: bool = True
    paid_leave: bool = True
    gender_restriction: GenderRestriction = GenderRestriction.ALL
    minimum_service_days: int = Field(0, ge=0)


class LeaveTypeUpdate(BaseModel):
    leave_name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    annual_quota: int | None = Field(None, ge=0)
    carry_forward: bool | None = None
    maximum_carry_forward: int | None = Field(None, ge=0)
    encashment_allowed: bool | None = None
    requires_attachment: bool | None = None
    requires_approval: bool | None = None
    paid_leave: bool | None = None
    gender_restriction: GenderRestriction | None = None
    minimum_service_days: int | None = Field(None, ge=0)
    status: LeaveStatus | None = None
    is_active: bool | None = None


class LeaveTypeResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    leave_code: str
    leave_name: str
    description: str | None
    annual_quota: int
    carry_forward: bool
    maximum_carry_forward: int
    encashment_allowed: bool
    requires_attachment: bool
    requires_approval: bool
    paid_leave: bool
    gender_restriction: GenderRestriction
    minimum_service_days: int
    status: LeaveStatus
    is_active: bool
    is_locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Leave Policy Schemas
class LeavePolicyCreate(BaseModel):
    leave_type_id: uuid.UUID
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employee_type: str | None = Field(None, max_length=50)
    probation_rules: str | None = None
    carry_forward_rules: str | None = None
    monthly_accrual: bool = False
    accrual_rate: float = Field(0.00, ge=0.0)
    allow_half_day: bool = True
    max_consecutive_days: int | None = Field(None, ge=1)
    minimum_notice_days: int = Field(0, ge=0)


class LeavePolicyUpdate(BaseModel):
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employee_type: str | None = Field(None, max_length=50)
    probation_rules: str | None = None
    carry_forward_rules: str | None = None
    monthly_accrual: bool | None = None
    accrual_rate: float | None = Field(None, ge=0.0)
    allow_half_day: bool | None = None
    max_consecutive_days: int | None = Field(None, ge=1)
    minimum_notice_days: int | None = Field(None, ge=0)
    status: LeaveStatus | None = None
    is_active: bool | None = None


class LeavePolicyResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    leave_type_id: uuid.UUID
    department_id: uuid.UUID | None
    designation_id: uuid.UUID | None
    employee_type: str | None
    probation_rules: str | None
    carry_forward_rules: str | None
    monthly_accrual: bool
    accrual_rate: float
    allow_half_day: bool
    max_consecutive_days: int | None
    minimum_notice_days: int
    status: LeaveStatus
    is_active: bool
    is_locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Leave Balance Schemas
class LeaveBalanceUpdate(BaseModel):
    opening_balance: float | None = Field(None, ge=0.0)
    earned: float | None = Field(None, ge=0.0)
    used: float | None = Field(None, ge=0.0)
    carry_forward: float | None = Field(None, ge=0.0)


class LeaveBalanceResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    opening_balance: float
    earned: float
    used: float
    carry_forward: float
    remaining_balance: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Leave Request and Approvals
class LeaveAttachmentResponse(BaseModel):
    id: uuid.UUID
    file_name: str
    file_path: str
    file_size: int
    mime_type: str

    model_config = ConfigDict(from_attributes=True)


class LeaveApprovalResponse(BaseModel):
    id: uuid.UUID
    approver_id: uuid.UUID
    approval_level: int
    status: ApprovalStatus
    remarks: str | None
    approval_date: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestCreate(BaseModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    half_day: bool = False
    half_day_session: HalfDaySession | None = None
    reason: str = Field(..., min_length=5)


class LeaveRequestResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    total_days: float
    half_day: bool
    half_day_session: HalfDaySession | None
    reason: str
    status: LeaveRequestStatus
    submitted_date: datetime
    approved_date: datetime | None
    cancelled_date: datetime | None
    created_at: datetime
    updated_at: datetime
    approvals: list[LeaveApprovalResponse] = []
    attachments: list[LeaveAttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


# Holiday Calendar Schemas
class HolidayCalendarCreate(BaseModel):
    holiday_date: date
    holiday_name: str = Field(..., min_length=2, max_length=150)
    holiday_type: HolidayType = HolidayType.PUBLIC
    description: str | None = None


class HolidayCalendarUpdate(BaseModel):
    holiday_date: date | None = None
    holiday_name: str | None = Field(None, min_length=2, max_length=150)
    holiday_type: HolidayType | None = None
    description: str | None = None
    is_active: bool | None = None


class HolidayCalendarResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    holiday_date: date
    holiday_name: str
    holiday_type: HolidayType
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
