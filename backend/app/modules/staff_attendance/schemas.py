import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.staff_attendance.enums import (
    AttendancePolicyStatus,
    AttendanceSource,
    AttendanceStatus,
    DeviceStatus,
    DeviceType,
    LogSource,
    RegularizationStatus,
    ShiftStatus,
)

# ---------------------------------------------------------------------------
# AttendanceShift schemas
# ---------------------------------------------------------------------------


class AttendanceShiftCreate(BaseModel):
    shift_code: str = Field(..., min_length=1, max_length=50)
    shift_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None
    grace_minutes: int = Field(default=0, ge=0, le=120)
    working_hours: float = Field(default=8.0, gt=0, le=24)
    is_night_shift: bool = False
    is_active: bool = True


class AttendanceShiftUpdate(BaseModel):
    shift_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    break_start: time | None = None
    break_end: time | None = None
    grace_minutes: int | None = Field(default=None, ge=0, le=120)
    working_hours: float | None = Field(default=None, gt=0, le=24)
    is_night_shift: bool | None = None
    is_active: bool | None = None
    status: ShiftStatus | None = None


class AttendanceShiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    shift_code: str
    shift_name: str
    description: str | None
    start_time: time
    end_time: time
    break_start: time | None
    break_end: time | None
    grace_minutes: int
    working_hours: float
    is_night_shift: bool
    status: ShiftStatus
    is_active: bool
    is_locked: bool
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# AttendancePolicy schemas
# ---------------------------------------------------------------------------


class AttendancePolicyCreate(BaseModel):
    policy_name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    late_arrival_threshold_minutes: int = Field(default=15, ge=0)
    late_arrival_deduction_minutes: int = Field(default=0, ge=0)
    early_departure_threshold_minutes: int = Field(default=15, ge=0)
    early_departure_deduction_minutes: int = Field(default=0, ge=0)
    overtime_threshold_minutes: int = Field(default=30, ge=0)
    overtime_enabled: bool = False
    weekend_days: str = Field(default="SAT,SUN", max_length=20)
    count_holidays_as_present: bool = True
    count_weekends_as_present: bool = False
    grace_period_minutes: int = Field(default=0, ge=0, le=120)
    auto_half_day_threshold_minutes: int | None = None
    auto_half_day_enabled: bool = False
    auto_absent_threshold_minutes: int | None = None
    auto_absent_enabled: bool = False
    is_default: bool = False

    @field_validator("weekend_days")
    @classmethod
    def validate_weekend_days(cls, v: str) -> str:
        valid = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        days = [d.strip().upper() for d in v.split(",") if d.strip()]
        invalid = set(days) - valid
        if invalid:
            raise ValueError(
                f"Invalid day codes: {invalid}. Use MON,TUE,WED,THU,FRI,SAT,SUN."
            )
        return ",".join(days)


class AttendancePolicyUpdate(BaseModel):
    policy_name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    late_arrival_threshold_minutes: int | None = Field(default=None, ge=0)
    late_arrival_deduction_minutes: int | None = Field(default=None, ge=0)
    early_departure_threshold_minutes: int | None = Field(default=None, ge=0)
    early_departure_deduction_minutes: int | None = Field(default=None, ge=0)
    overtime_threshold_minutes: int | None = Field(default=None, ge=0)
    overtime_enabled: bool | None = None
    weekend_days: str | None = Field(default=None, max_length=20)
    count_holidays_as_present: bool | None = None
    count_weekends_as_present: bool | None = None
    grace_period_minutes: int | None = Field(default=None, ge=0, le=120)
    auto_half_day_threshold_minutes: int | None = None
    auto_half_day_enabled: bool | None = None
    auto_absent_threshold_minutes: int | None = None
    auto_absent_enabled: bool | None = None
    is_default: bool | None = None
    status: AttendancePolicyStatus | None = None


class AttendancePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    policy_name: str
    description: str | None
    late_arrival_threshold_minutes: int
    late_arrival_deduction_minutes: int
    early_departure_threshold_minutes: int
    early_departure_deduction_minutes: int
    overtime_threshold_minutes: int
    overtime_enabled: bool
    weekend_days: str
    count_holidays_as_present: bool
    count_weekends_as_present: bool
    grace_period_minutes: int
    auto_half_day_threshold_minutes: int | None
    auto_half_day_enabled: bool
    auto_absent_threshold_minutes: int | None
    auto_absent_enabled: bool
    status: AttendancePolicyStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# AttendanceRecord schemas
# ---------------------------------------------------------------------------


class AttendanceRecordCreate(BaseModel):
    employee_id: uuid.UUID
    shift_id: uuid.UUID | None = None
    attendance_date: date
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    status: AttendanceStatus = AttendanceStatus.PRESENT
    source: AttendanceSource = AttendanceSource.MANUAL
    remarks: str | None = None


class AttendanceRecordUpdate(BaseModel):
    shift_id: uuid.UUID | None = None
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    status: AttendanceStatus | None = None
    remarks: str | None = None


class AttendanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID | None
    attendance_date: date
    check_in_time: datetime | None
    check_out_time: datetime | None
    working_hours: float
    late_minutes: int
    early_departure_minutes: int
    overtime_minutes: int
    status: AttendanceStatus
    source: AttendanceSource
    remarks: str | None
    is_locked: bool
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# AttendanceRegularization schemas
# ---------------------------------------------------------------------------


class RegularizationCreate(BaseModel):
    attendance_record_id: uuid.UUID
    reason: str = Field(..., min_length=5, max_length=1000)
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    requested_status: AttendanceStatus | None = None


class RegularizationUpdate(BaseModel):
    reason: str | None = Field(default=None, min_length=5, max_length=1000)
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    requested_status: AttendanceStatus | None = None


class RegularizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    attendance_record_id: uuid.UUID
    reason: str
    requested_check_in: datetime | None
    requested_check_out: datetime | None
    requested_status: AttendanceStatus | None
    approver_id: uuid.UUID | None
    approval_status: RegularizationStatus
    approval_remarks: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class RegularizationApproveReject(BaseModel):
    remarks: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# AttendanceDevice schemas
# ---------------------------------------------------------------------------


class AttendanceDeviceCreate(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=150)
    device_type: DeviceType
    serial_number: str | None = Field(default=None, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class AttendanceDeviceUpdate(BaseModel):
    device_name: str | None = Field(default=None, min_length=1, max_length=150)
    device_type: DeviceType | None = None
    serial_number: str | None = Field(default=None, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    location: str | None = Field(default=None, max_length=200)
    status: DeviceStatus | None = None
    notes: str | None = None


class AttendanceDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    device_name: str
    device_type: DeviceType
    serial_number: str | None
    ip_address: str | None
    location: str | None
    status: DeviceStatus
    last_sync_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# AttendanceLog schemas
# ---------------------------------------------------------------------------


class AttendanceLogCreate(BaseModel):
    employee_id: uuid.UUID
    device_id: uuid.UUID | None = None
    log_timestamp: datetime
    source: LogSource = LogSource.MANUAL
    raw_data: str | None = None
    notes: str | None = None


class AttendanceLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    device_id: uuid.UUID | None
    log_timestamp: datetime
    source: LogSource
    raw_data: str | None
    is_processed: bool
    processed_record_id: uuid.UUID | None
    notes: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Attendance Summary schema
# ---------------------------------------------------------------------------


class AttendanceSummary(BaseModel):
    employee_id: uuid.UUID
    month: int
    year: int
    total_days: int
    present_days: int
    absent_days: int
    half_days: int
    late_days: int
    on_leave_days: int
    holidays: int
    weekends: int
    total_working_hours: float
    total_overtime_minutes: int
