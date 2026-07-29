import uuid
from datetime import date, datetime
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity
from app.modules.leave.enums import (
    ApprovalStatus,
    GenderRestriction,
    HalfDaySession,
    HolidayType,
    LeaveRequestStatus,
    LeaveStatus,
)

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.modules.department.models import Department
    from app.modules.designation.models import Designation
    from app.modules.employee.models import Employee


class LeaveType(BaseEntity):
    """
    SQLAlchemy Model representing classifications of leaves configured for a school.
    """

    __tablename__ = "leave_types"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_code: Mapped[str] = mapped_column(String(50), nullable=False)
    leave_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    annual_quota: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    carry_forward: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    maximum_carry_forward: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    encashment_allowed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    requires_attachment: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    paid_leave: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    gender_restriction: Mapped[GenderRestriction] = mapped_column(
        Enum(GenderRestriction, name="leave_gender_restriction"),
        default=GenderRestriction.ALL,
        nullable=False,
    )
    minimum_service_days: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, name="leave_status"),
        default=LeaveStatus.ACTIVE,
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
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], backref="created_leave_types"
    )
    updater: Mapped["User"] = relationship(
        "User", foreign_keys=[updated_by], backref="updated_leave_types"
    )


class LeavePolicy(BaseEntity):
    """
    SQLAlchemy Model representing eligibility and probation rules governing leave access.
    """

    __tablename__ = "leave_policies"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("designations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    employee_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    probation_rules: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON config string
    carry_forward_rules: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON config string

    monthly_accrual: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    accrual_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, nullable=False
    )
    allow_half_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_consecutive_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_notice_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, name="leave_policy_status"),
        default=LeaveStatus.ACTIVE,
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
    leave_type: Mapped[LeaveType] = relationship(LeaveType)
    department: Mapped["Department | None"] = relationship("Department")
    designation: Mapped["Designation | None"] = relationship("Designation")


class LeaveBalance(BaseEntity):
    """
    SQLAlchemy Model representing current quotas, carry forwards, and remaining leaves of an Employee.
    """

    __tablename__ = "leave_balances"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    opening_balance: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, nullable=False
    )
    earned: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, nullable=False)
    used: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, nullable=False)
    carry_forward: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, nullable=False
    )
    remaining_balance: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, nullable=False
    )

    # Relationships
    school: Mapped["School"] = relationship("School")
    employee: Mapped["Employee"] = relationship("Employee")
    leave_type: Mapped[LeaveType] = relationship(LeaveType)


class LeaveRequest(BaseEntity):
    """
    SQLAlchemy Model representing a submitted leave request of an Employee.
    """

    __tablename__ = "leave_requests"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    half_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    half_day_session: Mapped[HalfDaySession | None] = mapped_column(
        Enum(HalfDaySession, name="leave_half_day_session"), nullable=True
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveRequestStatus] = mapped_column(
        Enum(LeaveRequestStatus, name="leave_request_status"),
        default=LeaveRequestStatus.PENDING,
        nullable=False,
        index=True,
    )

    submitted_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    approved_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_date: Mapped[datetime | None] = mapped_column(
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
    employee: Mapped["Employee"] = relationship("Employee", lazy="selectin")
    leave_type: Mapped[LeaveType] = relationship(LeaveType, lazy="selectin")
    approvals: Mapped[list["LeaveApproval"]] = relationship(
        "LeaveApproval",
        back_populates="leave_request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    attachments: Mapped[list["LeaveAttachment"]] = relationship(
        "LeaveAttachment",
        back_populates="leave_request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LeaveApproval(BaseEntity):
    """
    SQLAlchemy Model representing the multi-level workflow decisions on a LeaveRequest.
    """

    __tablename__ = "leave_approvals"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    approval_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="leave_approval_status"),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    leave_request: Mapped[LeaveRequest] = relationship(
        LeaveRequest, back_populates="approvals"
    )
    approver: Mapped["User"] = relationship("User")


class LeaveAttachment(BaseEntity):
    """
    SQLAlchemy Model representing uploaded supporting documentation for medical or long leaves.
    """

    __tablename__ = "leave_attachments"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    leave_request: Mapped[LeaveRequest] = relationship(
        LeaveRequest, back_populates="attachments"
    )


class HolidayCalendar(BaseEntity):
    """
    SQLAlchemy Model representing academic, public, weekend or regional holidays.
    """

    __tablename__ = "holiday_calendar"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    holiday_name: Mapped[str] = mapped_column(String(150), nullable=False)
    holiday_type: Mapped[HolidayType] = mapped_column(
        Enum(HolidayType, name="leave_holiday_type"),
        default=HolidayType.PUBLIC,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    school: Mapped["School"] = relationship("School")


# Unique Indexes
Index(
    "ix_uq_school_leave_code",
    LeaveType.school_id,
    LeaveType.leave_code,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_leave_balance",
    LeaveBalance.school_id,
    LeaveBalance.employee_id,
    LeaveBalance.leave_type_id,
    LeaveBalance.year,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
Index(
    "ix_uq_school_holiday_date",
    HolidayCalendar.school_id,
    HolidayCalendar.holiday_date,
    unique=True,
    postgresql_where=text("is_deleted = false"),
)
