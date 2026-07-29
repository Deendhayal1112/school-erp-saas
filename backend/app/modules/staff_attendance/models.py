import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
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

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.employee.models import Employee


class AttendanceShift(BaseEntity):
    """
    SQLAlchemy Model defining a named work shift with time windows, break periods
    and grace margins used to classify employee attendance records.
    """

    __tablename__ = "attendance_shifts"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_code: Mapped[str] = mapped_column(String(50), nullable=False)
    shift_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    break_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    grace_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Effective hours excluding breaks (stored in hours as decimal)
    working_hours: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=8.0
    )
    is_night_shift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus, name="attendance_shift_status"),
        default=ShiftStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")

    __table_args__ = (
        Index(
            "ix_uq_school_shift_code",
            "school_id",
            "shift_code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )


class AttendancePolicy(BaseEntity):
    """
    SQLAlchemy Model capturing school-level attendance rules for late arrivals,
    early departures, overtime calculation, auto half-day, and auto absent thresholds.
    """

    __tablename__ = "attendance_policies"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Late arrival rules
    late_arrival_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    late_arrival_deduction_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # Early departure rules
    early_departure_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    early_departure_deduction_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # Overtime rules
    overtime_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    overtime_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Weekend and holiday rules
    weekend_days: Mapped[str] = mapped_column(
        String(20), default="SAT,SUN", nullable=False
    )  # Comma-separated day codes
    count_holidays_as_present: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    count_weekends_as_present: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Grace period
    grace_period_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # Auto half-day rule: if late by X mins or more → HALF_DAY
    auto_half_day_threshold_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    auto_half_day_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Auto absent rule: if late by X mins or more → ABSENT
    auto_absent_threshold_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    auto_absent_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    status: Mapped[AttendancePolicyStatus] = mapped_column(
        Enum(AttendancePolicyStatus, name="attendance_policy_status"),
        default=AttendancePolicyStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")


class AttendanceRecord(BaseEntity):
    """
    SQLAlchemy Model representing a single day's attendance for one employee,
    capturing check-in / check-out times, computed time metrics, and status.
    """

    __tablename__ = "attendance_records"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_shifts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    check_in_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Computed fields (populated by service layer)
    working_hours: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.0, nullable=False
    )
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    early_departure_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_record_status"),
        default=AttendanceStatus.ABSENT,
        nullable=False,
        index=True,
    )
    source: Mapped[AttendanceSource] = mapped_column(
        Enum(AttendanceSource, name="attendance_source"),
        default=AttendanceSource.MANUAL,
        nullable=False,
        index=True,
    )

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    employee: Mapped["Employee"] = relationship("Employee", lazy="selectin")
    shift: Mapped["AttendanceShift | None"] = relationship(
        "AttendanceShift", lazy="selectin"
    )
    regularizations: Mapped[list["AttendanceRegularization"]] = relationship(
        "AttendanceRegularization",
        back_populates="attendance_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_uq_employee_attendance_date",
            "school_id",
            "employee_id",
            "attendance_date",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )


class AttendanceRegularization(BaseEntity):
    """
    SQLAlchemy Model for an employee's request to correct or justify an attendance
    anomaly (e.g., forgotten check-in) through an approval workflow.
    """

    __tablename__ = "attendance_regularizations"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attendance_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    requested_check_in: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_check_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_status: Mapped[AttendanceStatus | None] = mapped_column(
        Enum(AttendanceStatus, name="regularization_requested_status"),
        nullable=True,
    )

    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approval_status: Mapped[RegularizationStatus] = mapped_column(
        Enum(RegularizationStatus, name="regularization_approval_status"),
        default=RegularizationStatus.PENDING,
        nullable=False,
        index=True,
    )
    approval_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    employee: Mapped["Employee"] = relationship(
        "Employee", foreign_keys=[employee_id], lazy="selectin"
    )
    attendance_record: Mapped["AttendanceRecord"] = relationship(
        "AttendanceRecord", back_populates="regularizations"
    )
    approver: Mapped["User | None"] = relationship(
        "User", foreign_keys=[approver_id], lazy="selectin"
    )


class AttendanceDevice(BaseEntity):
    """
    SQLAlchemy Model representing a physical or virtual attendance capture device
    (biometric, RFID, mobile) registered for a school.
    """

    __tablename__ = "attendance_devices"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_name: Mapped[str] = mapped_column(String(150), nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(
        Enum(DeviceType, name="attendance_device_type"),
        nullable=False,
        index=True,
    )
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="attendance_device_status"),
        default=DeviceStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_uq_school_device_serial",
            "school_id",
            "serial_number",
            unique=True,
            postgresql_where=text("is_deleted = false AND serial_number IS NOT NULL"),
        ),
    )


class AttendanceLog(BaseEntity):
    """
    SQLAlchemy Model capturing raw attendance log entries from biometric devices,
    API calls, or manual entries before they are processed into AttendanceRecord rows.
    """

    __tablename__ = "attendance_logs"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    log_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source: Mapped[LogSource] = mapped_column(
        Enum(LogSource, name="attendance_log_source"),
        nullable=False,
        index=True,
    )
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_records.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    employee: Mapped["Employee"] = relationship("Employee", lazy="selectin")
    device: Mapped["AttendanceDevice | None"] = relationship(
        "AttendanceDevice", back_populates="logs"
    )
