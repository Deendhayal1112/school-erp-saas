import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.employee.models import Employee
from app.modules.leave.enums import (
    ApprovalStatus,
    HalfDaySession,
    LeaveRequestStatus,
)
from app.modules.leave.exceptions import (
    InvalidLeaveDataException,
    LeaveNotFoundException,
)
from app.modules.leave.models import (
    HolidayCalendar,
    LeaveApproval,
    LeaveBalance,
    LeavePolicy,
    LeaveRequest,
    LeaveType,
)
from app.modules.leave.repository import LeaveRepository
from app.modules.leave.validators import (
    validate_half_day,
    validate_leave_policy,
    validate_leave_request_dates,
    validate_leave_type,
)
from app.storage.service import FileStorageService

logger = logging.getLogger(__name__)


class LeaveService:
    """
    Service layer coordinating leave type, policy, balance, requests and multi-level approvals.
    """

    def __init__(
        self,
        db: AsyncSession,
        cache: CacheService | None = None,
        storage: FileStorageService | None = None,
    ) -> None:
        self.db = db
        self.repo = LeaveRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()
        self.storage = storage or FileStorageService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, employee_id: uuid.UUID | None = None
    ) -> None:
        await self.cache.delete_pattern("leave:*")

    # 1. Leave Type Methods
    async def create_leave_type(
        self, body: Any, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> LeaveType:
        validate_leave_type(body.leave_code, body.leave_name)

        # Check code duplicate
        exists = await self.repo.get_leave_type_by_code(
            body.leave_code.strip(), school_id
        )
        if exists:
            raise InvalidLeaveDataException(
                f"Leave code '{body.leave_code}' already exists in this school"
            )

        lt = LeaveType(
            school_id=school_id,
            leave_code=body.leave_code.strip().upper(),
            leave_name=body.leave_name.strip(),
            description=body.description,
            annual_quota=body.annual_quota,
            carry_forward=body.carry_forward,
            maximum_carry_forward=body.maximum_carry_forward,
            encashment_allowed=body.encashment_allowed,
            requires_attachment=body.requires_attachment,
            requires_approval=body.requires_approval,
            paid_leave=body.paid_leave,
            gender_restriction=body.gender_restriction,
            minimum_service_days=body.minimum_service_days,
            created_by=user_id,
            updated_by=user_id,
        )
        await self.repo.create_leave_type(lt)
        await self.db.flush()

        await self._invalidate_cache(school_id)
        return lt

    # 2. Leave Policy Methods
    async def create_leave_policy(
        self, body: Any, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> LeavePolicy:
        validate_leave_policy(
            body.max_consecutive_days, body.minimum_notice_days, body.accrual_rate
        )

        lt = await self.repo.get_leave_type_by_id(body.leave_type_id, school_id)
        if not lt:
            raise LeaveNotFoundException("Leave type not found")

        lp = LeavePolicy(
            school_id=school_id,
            leave_type_id=body.leave_type_id,
            department_id=body.department_id,
            designation_id=body.designation_id,
            employee_type=body.employee_type,
            probation_rules=body.probation_rules,
            carry_forward_rules=body.carry_forward_rules,
            monthly_accrual=body.monthly_accrual,
            accrual_rate=body.accrual_rate,
            allow_half_day=body.allow_half_day,
            max_consecutive_days=body.max_consecutive_days,
            minimum_notice_days=body.minimum_notice_days,
            created_by=user_id,
            updated_by=user_id,
        )
        await self.repo.create_leave_policy(lp)
        await self.db.flush()

        await self._invalidate_cache(school_id)
        return lp

    # 3. Holiday Calendar Methods
    async def create_holiday(
        self, body: Any, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> HolidayCalendar:
        # Check duplicate date
        exists = await self.repo.get_holiday_by_date(body.holiday_date, school_id)
        if exists:
            raise InvalidLeaveDataException(
                f"Holiday already configured for date {body.holiday_date}"
            )

        hc = HolidayCalendar(
            school_id=school_id,
            holiday_date=body.holiday_date,
            holiday_name=body.holiday_name.strip(),
            holiday_type=body.holiday_type,
            description=body.description,
            created_by=user_id,
            updated_by=user_id,
        )
        await self.repo.create_holiday(hc)
        await self.db.flush()

        await self._invalidate_cache(school_id)
        return hc

    # 4. Working Days Calculation
    async def calculate_working_days(
        self, school_id: uuid.UUID, start_date: date, end_date: date
    ) -> float:
        """Returns count of active working days in interval, excluding weekends and calendar holidays."""
        if start_date > end_date:
            return 0.0

        # Fetch holidays in range
        holiday_dates = await self.repo.get_holidays_in_range(
            school_id, start_date, end_date
        )
        holiday_set = set(holiday_dates)

        total_days = 0.0
        current = start_date
        while current <= end_date:
            # 0 = Monday, 6 = Sunday (so 5=Saturday, 6=Sunday)
            weekday = current.weekday()
            if weekday < 5 and current not in holiday_set:
                total_days += 1.0
            current += timedelta(days=1)

        return total_days

    # 5. Apply Leave Request
    async def apply_leave_request(
        self,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        start_date: date,
        end_date: date,
        reason: str,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        half_day: bool = False,
        half_day_session: HalfDaySession | None = None,
    ) -> LeaveRequest:
        # 1. Validation
        validate_leave_request_dates(start_date, end_date)
        validate_half_day(half_day, half_day_session)

        # Check employee exists in tenant
        emp = await self.db.get(Employee, employee_id)
        if not emp or emp.is_deleted or emp.school_id != school_id:
            raise InvalidLeaveDataException("Employee not found in school")

        # Check leave type exists in tenant
        lt = await self.repo.get_leave_type_by_id(leave_type_id, school_id)
        if not lt:
            raise LeaveNotFoundException("Leave type not found")

        # Overlap check
        has_overlap = await self.repo.has_overlapping_request(
            employee_id, start_date, end_date
        )
        if has_overlap:
            raise InvalidLeaveDataException(
                "Leave request overlaps with an existing request"
            )

        # Notice period policy check
        today = date.today()
        notice_days = (start_date - today).days
        # Find applicable policy
        policies = await self.repo.list_leave_policies(
            school_id=school_id,
            leave_type_id=leave_type_id,
            department_id=emp.department_id,
            designation_id=emp.designation_id,
        )
        policy = policies[0] if policies else None

        if policy:
            if notice_days < policy.minimum_notice_days:
                raise InvalidLeaveDataException(
                    f"Notice period violation. Minimum required: {policy.minimum_notice_days} days. Provided: {notice_days} days."
                )
            if half_day and not policy.allow_half_day:
                raise InvalidLeaveDataException(
                    "Half-day leaves are not allowed for this leave type"
                )

        # 2. Compute requested days
        if half_day:
            if start_date != end_date:
                raise InvalidLeaveDataException(
                    "Half-day leaves must have matching start and end dates"
                )
            total_days = 0.5
        else:
            total_days = await self.calculate_working_days(
                school_id, start_date, end_date
            )
            if total_days <= 0:
                raise InvalidLeaveDataException(
                    "No working days found in requested date range"
                )

        if policy and policy.max_consecutive_days:
            if total_days > policy.max_consecutive_days:
                raise InvalidLeaveDataException(
                    f"Maximum consecutive days limit exceeded. Limit: {policy.max_consecutive_days} days."
                )

        # 3. Quota Balance Check
        year = start_date.year
        bal = await self.repo.get_leave_balance(
            school_id, employee_id, leave_type_id, year
        )
        if not bal:
            # Lazy initialize balance for the employee
            bal = LeaveBalance(
                school_id=school_id,
                employee_id=employee_id,
                leave_type_id=leave_type_id,
                year=year,
                opening_balance=float(lt.annual_quota),
                remaining_balance=float(lt.annual_quota),
            )
            await self.repo.create_leave_balance(bal)
            await self.db.flush()

        if float(bal.remaining_balance) < total_days:
            raise InvalidLeaveDataException("Insufficient leave balance quota")

        # 4. Save Request
        lr = LeaveRequest(
            school_id=school_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            half_day=half_day,
            half_day_session=half_day_session,
            reason=reason.strip(),
            status=LeaveRequestStatus.PENDING,
            created_by=user_id,
            updated_by=user_id,
        )

        await self.repo.create_leave_request(lr)
        await self.db.flush()

        await self._invalidate_cache(school_id, employee_id)

        # Log audit
        await self.audit.log_action(
            module="leave",
            action="apply_request",
            entity_name="LeaveRequest",
            entity_id=lr.id,
            user_id=user_id,
            school_id=school_id,
        )

        return lr

    # 6. Approve Leave Request Workflow
    async def approve_leave_request(
        self,
        lr_id: uuid.UUID,
        remarks: str | None,
        current_user: User,
    ) -> LeaveRequest:
        lr = await self.repo.get_leave_request_by_id(lr_id, current_user.school_id)
        if not lr:
            raise LeaveNotFoundException("Leave request not found")

        if lr.status != LeaveRequestStatus.PENDING:
            raise InvalidLeaveDataException("Can only approve pending leave requests")

        # Prevent self-approval
        # If user has an associated employee profile, check if employee matches
        # Normally a user might approve their own request if they have admin privileges, but domain rules forbid it.
        # Check if the user is the applicant of this leave
        if current_user.email == lr.employee.email:
            raise InvalidLeaveDataException("Cannot approve own leave request")

        # Balance check
        year = lr.start_date.year
        bal = await self.repo.get_leave_balance(
            current_user.school_id, lr.employee_id, lr.leave_type_id, year
        )
        if not bal or float(bal.remaining_balance) < float(lr.total_days):
            raise InvalidLeaveDataException("Insufficient leave balance quota")

        # Create approval record
        approval = LeaveApproval(
            school_id=current_user.school_id,
            leave_request_id=lr.id,
            approver_id=current_user.id,
            approval_level=1,
            status=ApprovalStatus.APPROVED,
            remarks=remarks.strip() if remarks else None,
            approval_date=datetime.now(),
        )
        self.db.add(approval)

        # Update balance
        bal.used = float(bal.used) + float(lr.total_days)
        bal.remaining_balance = float(bal.remaining_balance) - float(lr.total_days)
        self.db.add(bal)

        # Approve request
        lr.status = LeaveRequestStatus.APPROVED
        lr.approved_date = datetime.now()
        lr.updated_by = current_user.id
        self.db.add(lr)

        await self.db.flush()
        await self._invalidate_cache(current_user.school_id, lr.employee_id)

        # Log audit
        await self.audit.log_action(
            module="leave",
            action="approve",
            entity_name="LeaveRequest",
            entity_id=lr.id,
            user_id=current_user.id,
            school_id=current_user.school_id,
        )

        return lr

    # 7. Reject Leave Request
    async def reject_leave_request(
        self,
        lr_id: uuid.UUID,
        remarks: str | None,
        current_user: User,
    ) -> LeaveRequest:
        lr = await self.repo.get_leave_request_by_id(lr_id, current_user.school_id)
        if not lr:
            raise LeaveNotFoundException("Leave request not found")

        if lr.status != LeaveRequestStatus.PENDING:
            raise InvalidLeaveDataException("Can only reject pending leave requests")

        approval = LeaveApproval(
            school_id=current_user.school_id,
            leave_request_id=lr.id,
            approver_id=current_user.id,
            approval_level=1,
            status=ApprovalStatus.REJECTED,
            remarks=remarks.strip() if remarks else None,
            approval_date=datetime.now(),
        )
        self.db.add(approval)

        # Reject request
        lr.status = LeaveRequestStatus.REJECTED
        lr.updated_by = current_user.id
        self.db.add(lr)

        await self.db.flush()
        await self._invalidate_cache(current_user.school_id, lr.employee_id)

        # Log audit
        await self.audit.log_action(
            module="leave",
            action="reject",
            entity_name="LeaveRequest",
            entity_id=lr.id,
            user_id=current_user.id,
            school_id=current_user.school_id,
        )

        return lr

    # 8. Cancel Leave Request
    async def cancel_leave_request(
        self,
        lr_id: uuid.UUID,
        current_user: User,
    ) -> LeaveRequest:
        lr = await self.repo.get_leave_request_by_id(lr_id, current_user.school_id)
        if not lr:
            raise LeaveNotFoundException("Leave request not found")

        if lr.status == LeaveRequestStatus.CANCELLED:
            raise InvalidLeaveDataException("Leave request is already cancelled")

        # Refund balances if previously approved
        if lr.status == LeaveRequestStatus.APPROVED:
            year = lr.start_date.year
            bal = await self.repo.get_leave_balance(
                current_user.school_id, lr.employee_id, lr.leave_type_id, year
            )
            if bal:
                bal.used = max(0.0, float(bal.used) - float(lr.total_days))
                bal.remaining_balance = float(bal.remaining_balance) + float(
                    lr.total_days
                )
                self.db.add(bal)

        # Set status
        lr.status = LeaveRequestStatus.CANCELLED
        lr.cancelled_date = datetime.now()
        lr.updated_by = current_user.id
        self.db.add(lr)

        await self.db.flush()
        await self._invalidate_cache(current_user.school_id, lr.employee_id)

        # Log audit
        await self.audit.log_action(
            module="leave",
            action="cancel",
            entity_name="LeaveRequest",
            entity_id=lr.id,
            user_id=current_user.id,
            school_id=current_user.school_id,
        )

        return lr

    # 9. Monthly Accrual Calculation
    async def accrue_monthly_leave(self, school_id: uuid.UUID) -> int:
        """Processes monthly accruals on active leave balances according to configured policy rates."""
        stmt = select(LeavePolicy).where(
            LeavePolicy.school_id == school_id,
            LeavePolicy.monthly_accrual == True,
            LeavePolicy.is_active == True,
        )
        policies = list((await self.db.execute(stmt)).scalars().all())
        if not policies:
            return 0

        accrued_count = 0
        year = date.today().year

        for policy in policies:
            # Query balances matching this policy type and school
            bal_stmt = select(LeaveBalance).where(
                LeaveBalance.school_id == school_id,
                LeaveBalance.leave_type_id == policy.leave_type_id,
                LeaveBalance.year == year,
                LeaveBalance.is_deleted == False,
            )
            balances = list((await self.db.execute(bal_stmt)).scalars().all())

            for bal in balances:
                rate = float(policy.accrual_rate)
                bal.earned = float(bal.earned) + rate
                bal.remaining_balance = float(bal.remaining_balance) + rate
                self.db.add(bal)
                accrued_count += 1

        if accrued_count > 0:
            await self.db.flush()
            await self._invalidate_cache(school_id)

        logger.info("Processed monthly leave accruals for %d balances.", accrued_count)
        return accrued_count
