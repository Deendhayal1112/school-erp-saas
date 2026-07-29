import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.staff_attendance.constants import (
    POLICY_CACHE_TTL,
    REGULARIZATION_WINDOW_DAYS,
    SHIFT_CACHE_TTL,
    SUMMARY_CACHE_TTL,
)
from app.modules.staff_attendance.enums import (
    AttendanceSource,
    AttendanceStatus,
    DeviceStatus,
    RegularizationStatus,
)
from app.modules.staff_attendance.exceptions import (
    AttendanceLockedError,
    AttendanceNotFoundException,
    DuplicateAttendanceException,
    InvalidAttendanceDataException,
    RegularizationNotEligibleException,
)
from app.modules.staff_attendance.models import (
    AttendanceDevice,
    AttendanceLog,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceRegularization,
    AttendanceShift,
)
from app.modules.staff_attendance.repository import AttendanceRepository
from app.modules.staff_attendance.schemas import (
    AttendanceDeviceCreate,
    AttendanceDeviceUpdate,
    AttendanceLogCreate,
    AttendancePolicyCreate,
    AttendancePolicyUpdate,
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceShiftCreate,
    AttendanceShiftUpdate,
    AttendanceSummary,
    RegularizationApproveReject,
    RegularizationCreate,
)
from app.modules.staff_attendance.validators import (
    validate_checkout_after_checkin,
    validate_grace_minutes,
    validate_shift_times,
)

logger = logging.getLogger(__name__)


class AttendanceService:
    """
    Service layer orchestrating all Staff Attendance business logic including
    shift management, policy enforcement, time metric calculation, regularization
    workflow, biometric log import, and monthly summary generation.
    """

    def __init__(
        self,
        db: AsyncSession,
        cache: CacheService | None = None,
    ) -> None:
        self.db = db
        self.repo = AttendanceRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    # -----------------------------------------------------------------------
    # Cache helpers
    # -----------------------------------------------------------------------

    async def _invalidate_shift_cache(self, school_id: uuid.UUID) -> None:
        await self.cache.delete(f"attendance:shifts:{school_id}")

    async def _invalidate_policy_cache(self, school_id: uuid.UUID) -> None:
        await self.cache.delete(f"attendance:policies:{school_id}")

    async def _invalidate_summary_cache(
        self, school_id: uuid.UUID, employee_id: uuid.UUID
    ) -> None:
        await self.cache.delete(f"attendance:summary:{school_id}:{employee_id}")

    # -----------------------------------------------------------------------
    # Calculation helpers
    # -----------------------------------------------------------------------

    def _compute_minutes_between(
        self, dt_start: datetime | None, dt_end: datetime | None
    ) -> float:
        """Returns total elapsed minutes between two datetimes, or 0."""
        if dt_start is None or dt_end is None:
            return 0.0
        delta = dt_end - dt_start
        return max(0.0, delta.total_seconds() / 60.0)

    def _compute_working_hours(
        self,
        check_in: datetime | None,
        check_out: datetime | None,
        shift: AttendanceShift | None,
    ) -> float:
        """Calculates effective working hours excluding break time."""
        if check_in is None or check_out is None:
            return 0.0
        total_minutes = self._compute_minutes_between(check_in, check_out)
        if shift and shift.break_start and shift.break_end:
            break_minutes = self._compute_minutes_between(
                datetime.combine(check_in.date(), shift.break_start),
                datetime.combine(check_in.date(), shift.break_end),
            )
            total_minutes = max(0.0, total_minutes - break_minutes)
        return round(total_minutes / 60.0, 2)

    def _compute_late_minutes(
        self,
        check_in: datetime | None,
        shift: AttendanceShift | None,
    ) -> int:
        """Returns how many minutes late an employee arrived vs shift start."""
        if check_in is None or shift is None:
            return 0
        scheduled_start = datetime.combine(check_in.date(), shift.start_time)
        # Respect timezone if check_in is tz-aware
        if check_in.tzinfo is not None:
            scheduled_start = scheduled_start.replace(tzinfo=check_in.tzinfo)
        effective_start = scheduled_start
        # Apply grace period
        from datetime import timedelta

        effective_start = scheduled_start + timedelta(minutes=shift.grace_minutes)
        if check_in > effective_start:
            return int((check_in - scheduled_start).total_seconds() / 60)
        return 0

    def _compute_early_departure_minutes(
        self,
        check_out: datetime | None,
        shift: AttendanceShift | None,
    ) -> int:
        """Returns how many minutes early an employee left vs shift end."""
        if check_out is None or shift is None:
            return 0
        scheduled_end = datetime.combine(check_out.date(), shift.end_time)
        if check_out.tzinfo is not None:
            scheduled_end = scheduled_end.replace(tzinfo=check_out.tzinfo)
        if check_out < scheduled_end:
            return int((scheduled_end - check_out).total_seconds() / 60)
        return 0

    def _compute_overtime_minutes(
        self,
        check_out: datetime | None,
        shift: AttendanceShift | None,
        policy: AttendancePolicy | None,
    ) -> int:
        """Returns overtime minutes if enabled and threshold exceeded."""
        if check_out is None or shift is None or policy is None:
            return 0
        if not policy.overtime_enabled:
            return 0
        scheduled_end = datetime.combine(check_out.date(), shift.end_time)
        if check_out.tzinfo is not None:
            scheduled_end = scheduled_end.replace(tzinfo=check_out.tzinfo)
        if check_out > scheduled_end:
            extra = int((check_out - scheduled_end).total_seconds() / 60)
            if extra >= policy.overtime_threshold_minutes:
                return extra
        return 0

    def _determine_status(
        self,
        check_in: datetime | None,
        late_minutes: int,
        early_minutes: int,
        policy: AttendancePolicy | None,
        requested_status: AttendanceStatus,
    ) -> AttendanceStatus:
        """Applies policy rules to auto-classify status."""
        if check_in is None:
            return AttendanceStatus.ABSENT
        if policy:
            if policy.auto_absent_enabled and policy.auto_absent_threshold_minutes:
                if late_minutes >= policy.auto_absent_threshold_minutes:
                    return AttendanceStatus.ABSENT
            if policy.auto_half_day_enabled and policy.auto_half_day_threshold_minutes:
                if late_minutes >= policy.auto_half_day_threshold_minutes:
                    return AttendanceStatus.HALF_DAY
        # Late classification
        if late_minutes > 0:
            return AttendanceStatus.LATE
        if early_minutes > 0:
            return AttendanceStatus.EARLY_DEPARTURE
        return requested_status

    # -----------------------------------------------------------------------
    # Shift CRUD
    # -----------------------------------------------------------------------

    async def create_shift(
        self,
        school_id: uuid.UUID,
        data: AttendanceShiftCreate,
        actor: User,
    ) -> AttendanceShift:
        validate_shift_times(
            data.start_time,
            data.end_time,
            data.break_start,
            data.break_end,
            data.is_night_shift,
        )
        validate_grace_minutes(data.grace_minutes)

        existing = await self.repo.get_shift_by_code(data.shift_code, school_id)
        if existing:
            raise InvalidAttendanceDataException(
                f"Shift code '{data.shift_code}' already exists."
            )

        shift = AttendanceShift(
            school_id=school_id,
            shift_code=data.shift_code.upper(),
            shift_name=data.shift_name,
            description=data.description,
            start_time=data.start_time,
            end_time=data.end_time,
            break_start=data.break_start,
            break_end=data.break_end,
            grace_minutes=data.grace_minutes,
            working_hours=data.working_hours,
            is_night_shift=data.is_night_shift,
            is_active=data.is_active,
            created_by=actor.id,
        )
        await self.repo.create_shift(shift)
        await self.db.flush()
        await self._invalidate_shift_cache(school_id)
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance_shift.create",
            entity_name="AttendanceShift",
            entity_id=shift.id,
            user_id=actor.id,
            school_id=school_id,
        )
        logger.info("Shift created: %s school=%s", shift.shift_code, school_id)
        return shift

    async def get_shift(
        self, shift_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceShift:
        shift = await self.repo.get_shift_by_id(shift_id, school_id)
        if not shift:
            raise AttendanceNotFoundException("Shift not found.")
        return shift

    async def list_shifts(
        self, school_id: uuid.UUID, active_only: bool = False
    ) -> list:
        cache_key = f"attendance:shifts:{school_id}:{active_only}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached  # type: ignore[return-value]
        shifts = await self.repo.list_shifts(school_id, active_only)
        from app.modules.staff_attendance.schemas import AttendanceShiftResponse

        serialized = [
            AttendanceShiftResponse.model_validate(s).model_dump(mode="json")
            for s in shifts
        ]
        await self.cache.set(cache_key, serialized, ttl=SHIFT_CACHE_TTL)
        return shifts

    async def update_shift(
        self,
        shift_id: uuid.UUID,
        school_id: uuid.UUID,
        data: AttendanceShiftUpdate,
        actor: User,
    ) -> AttendanceShift:
        shift = await self.get_shift(shift_id, school_id)
        if shift.is_locked:
            raise AttendanceLockedError("Shift is locked and cannot be modified.")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(shift, field, value)
        shift.updated_by = actor.id

        await self.db.flush()
        await self._invalidate_shift_cache(school_id)
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance_shift.update",
            entity_name="AttendanceShift",
            entity_id=shift.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return shift

    async def archive_shift(
        self, shift_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> AttendanceShift:
        shift = await self.get_shift(shift_id, school_id)
        await self.repo.archive_shift(shift)
        shift.updated_by = actor.id
        await self.db.flush()
        await self._invalidate_shift_cache(school_id)
        return shift

    # -----------------------------------------------------------------------
    # Policy CRUD
    # -----------------------------------------------------------------------

    async def create_policy(
        self,
        school_id: uuid.UUID,
        data: AttendancePolicyCreate,
        actor: User,
    ) -> AttendancePolicy:
        validate_grace_minutes(data.grace_period_minutes)
        policy = AttendancePolicy(
            school_id=school_id,
            policy_name=data.policy_name,
            description=data.description,
            late_arrival_threshold_minutes=data.late_arrival_threshold_minutes,
            late_arrival_deduction_minutes=data.late_arrival_deduction_minutes,
            early_departure_threshold_minutes=data.early_departure_threshold_minutes,
            early_departure_deduction_minutes=data.early_departure_deduction_minutes,
            overtime_threshold_minutes=data.overtime_threshold_minutes,
            overtime_enabled=data.overtime_enabled,
            weekend_days=data.weekend_days,
            count_holidays_as_present=data.count_holidays_as_present,
            count_weekends_as_present=data.count_weekends_as_present,
            grace_period_minutes=data.grace_period_minutes,
            auto_half_day_threshold_minutes=data.auto_half_day_threshold_minutes,
            auto_half_day_enabled=data.auto_half_day_enabled,
            auto_absent_threshold_minutes=data.auto_absent_threshold_minutes,
            auto_absent_enabled=data.auto_absent_enabled,
            is_default=data.is_default,
            created_by=actor.id,
        )
        await self.repo.create_policy(policy)
        await self.db.flush()
        await self._invalidate_policy_cache(school_id)
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance_policy.create",
            entity_name="AttendancePolicy",
            entity_id=policy.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return policy

    async def get_policy(
        self, policy_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendancePolicy:
        policy = await self.repo.get_policy_by_id(policy_id, school_id)
        if not policy:
            raise AttendanceNotFoundException("Policy not found.")
        return policy

    async def list_policies(self, school_id: uuid.UUID) -> list:
        cache_key = f"attendance:policies:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached  # type: ignore[return-value]
        policies = await self.repo.list_policies(school_id)
        from app.modules.staff_attendance.schemas import AttendancePolicyResponse

        serialized = [
            AttendancePolicyResponse.model_validate(p).model_dump(mode="json")
            for p in policies
        ]
        await self.cache.set(cache_key, serialized, ttl=POLICY_CACHE_TTL)
        return policies

    async def update_policy(
        self,
        policy_id: uuid.UUID,
        school_id: uuid.UUID,
        data: AttendancePolicyUpdate,
        actor: User,
    ) -> AttendancePolicy:
        policy = await self.get_policy(policy_id, school_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(policy, field, value)
        policy.updated_by = actor.id
        await self.db.flush()
        await self._invalidate_policy_cache(school_id)
        return policy

    # -----------------------------------------------------------------------
    # Attendance Record
    # -----------------------------------------------------------------------

    async def mark_attendance(
        self,
        school_id: uuid.UUID,
        data: AttendanceRecordCreate,
        actor: User,
    ) -> AttendanceRecord:
        # Duplicate check
        existing = await self.repo.get_record_by_employee_date(
            data.employee_id, data.attendance_date, school_id
        )
        if existing:
            raise DuplicateAttendanceException(
                f"Attendance already recorded for employee on {data.attendance_date}."
            )

        validate_checkout_after_checkin(data.check_in_time, data.check_out_time)

        # Fetch shift and default policy for metric computation
        shift: AttendanceShift | None = None
        if data.shift_id:
            shift = await self.repo.get_shift_by_id(data.shift_id, school_id)

        policy = await self.repo.get_default_policy(school_id)

        working_hours = self._compute_working_hours(
            data.check_in_time, data.check_out_time, shift
        )
        late_minutes = self._compute_late_minutes(data.check_in_time, shift)
        early_minutes = self._compute_early_departure_minutes(
            data.check_out_time, shift
        )
        overtime_minutes = self._compute_overtime_minutes(
            data.check_out_time, shift, policy
        )
        status = self._determine_status(
            data.check_in_time, late_minutes, early_minutes, policy, data.status
        )

        record = AttendanceRecord(
            school_id=school_id,
            employee_id=data.employee_id,
            shift_id=data.shift_id,
            attendance_date=data.attendance_date,
            check_in_time=data.check_in_time,
            check_out_time=data.check_out_time,
            working_hours=working_hours,
            late_minutes=late_minutes,
            early_departure_minutes=early_minutes,
            overtime_minutes=overtime_minutes,
            status=status,
            source=data.source,
            remarks=data.remarks,
            created_by=actor.id,
        )
        await self.repo.create_record(record)
        await self.db.flush()
        await self._invalidate_summary_cache(school_id, data.employee_id)
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance.mark",
            entity_name="AttendanceRecord",
            entity_id=record.id,
            user_id=actor.id,
            school_id=school_id,
        )
        logger.info(
            "Attendance marked: employee=%s date=%s status=%s",
            data.employee_id,
            data.attendance_date,
            status,
        )
        return record

    async def get_record(
        self, record_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceRecord:
        record = await self.repo.get_record_by_id(record_id, school_id)
        if not record:
            raise AttendanceNotFoundException("Attendance record not found.")
        return record

    async def list_records(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        shift_id: uuid.UUID | None = None,
        status: AttendanceStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AttendanceRecord]:
        return await self.repo.list_records(
            school_id=school_id,
            employee_id=employee_id,
            shift_id=shift_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

    async def update_record(
        self,
        record_id: uuid.UUID,
        school_id: uuid.UUID,
        data: AttendanceRecordUpdate,
        actor: User,
    ) -> AttendanceRecord:
        record = await self.get_record(record_id, school_id)
        if record.is_locked:
            raise AttendanceLockedError("Attendance record is locked.")

        # Re-validate check times if being updated
        new_in = (
            data.check_in_time
            if data.check_in_time is not None
            else record.check_in_time
        )
        new_out = (
            data.check_out_time
            if data.check_out_time is not None
            else record.check_out_time
        )
        validate_checkout_after_checkin(new_in, new_out)

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(record, field, value)

        # Recompute metrics
        shift: AttendanceShift | None = None
        if record.shift_id:
            shift = await self.repo.get_shift_by_id(record.shift_id, school_id)
        policy = await self.repo.get_default_policy(school_id)

        record.working_hours = self._compute_working_hours(
            record.check_in_time, record.check_out_time, shift
        )
        record.late_minutes = self._compute_late_minutes(record.check_in_time, shift)
        record.early_departure_minutes = self._compute_early_departure_minutes(
            record.check_out_time, shift
        )
        record.overtime_minutes = self._compute_overtime_minutes(
            record.check_out_time, shift, policy
        )
        record.updated_by = actor.id

        await self.db.flush()
        await self._invalidate_summary_cache(school_id, record.employee_id)
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance.update",
            entity_name="AttendanceRecord",
            entity_id=record.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return record

    async def get_attendance_summary(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        month: int,
        year: int,
    ) -> AttendanceSummary:
        cache_key = f"attendance:summary:{school_id}:{employee_id}:{year}:{month}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AttendanceSummary.model_validate(cached)

        records = await self.repo.get_monthly_records(
            school_id, employee_id, month, year
        )

        summary = AttendanceSummary(
            employee_id=employee_id,
            month=month,
            year=year,
            total_days=len(records),
            present_days=sum(
                1 for r in records if r.status == AttendanceStatus.PRESENT
            ),
            absent_days=sum(1 for r in records if r.status == AttendanceStatus.ABSENT),
            half_days=sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY),
            late_days=sum(1 for r in records if r.status == AttendanceStatus.LATE),
            on_leave_days=sum(
                1 for r in records if r.status == AttendanceStatus.ON_LEAVE
            ),
            holidays=sum(1 for r in records if r.status == AttendanceStatus.HOLIDAY),
            weekends=sum(1 for r in records if r.status == AttendanceStatus.WEEKEND),
            total_working_hours=sum(float(r.working_hours) for r in records),
            total_overtime_minutes=sum(r.overtime_minutes for r in records),
        )
        await self.cache.set(
            cache_key, summary.model_dump(mode="json"), ttl=SUMMARY_CACHE_TTL
        )
        return summary

    # -----------------------------------------------------------------------
    # Regularization workflow
    # -----------------------------------------------------------------------

    async def submit_regularization(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        data: RegularizationCreate,
        actor: User,
    ) -> AttendanceRegularization:
        record = await self.repo.get_record_by_id(data.attendance_record_id, school_id)
        if not record:
            raise AttendanceNotFoundException("Attendance record not found.")
        if record.is_locked:
            raise AttendanceLockedError()
        if record.employee_id != employee_id:
            raise RegularizationNotEligibleException(
                "Cannot regularize attendance for another employee."
            )

        # Window check
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=REGULARIZATION_WINDOW_DAYS)
        if record.attendance_date < cutoff:
            raise RegularizationNotEligibleException(
                f"Regularization window of {REGULARIZATION_WINDOW_DAYS} days has passed."
            )

        # Block duplicate pending request
        existing = await self.repo.get_pending_regularization_for_record(
            data.attendance_record_id, school_id
        )
        if existing:
            raise InvalidAttendanceDataException(
                "A pending regularization request already exists for this record."
            )

        if data.requested_check_in and data.requested_check_out:
            validate_checkout_after_checkin(
                data.requested_check_in, data.requested_check_out
            )

        reg = AttendanceRegularization(
            school_id=school_id,
            employee_id=employee_id,
            attendance_record_id=data.attendance_record_id,
            reason=data.reason,
            requested_check_in=data.requested_check_in,
            requested_check_out=data.requested_check_out,
            requested_status=data.requested_status,
            created_by=actor.id,
        )
        await self.repo.create_regularization(reg)
        await self.db.flush()
        await self.audit.log_action(
            module="staff_attendance",
            action="regularization.submit",
            entity_name="AttendanceRegularization",
            entity_id=reg.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return reg

    async def approve_regularization(
        self,
        reg_id: uuid.UUID,
        school_id: uuid.UUID,
        data: RegularizationApproveReject,
        actor: User,
    ) -> AttendanceRegularization:
        reg = await self.repo.get_regularization_by_id(reg_id, school_id)
        if not reg:
            raise AttendanceNotFoundException("Regularization request not found.")
        if reg.approval_status != RegularizationStatus.PENDING:
            raise InvalidAttendanceDataException(
                "Only PENDING regularizations can be approved."
            )

        reg.approval_status = RegularizationStatus.APPROVED
        reg.approver_id = actor.id
        reg.approval_remarks = data.remarks
        reg.approved_at = datetime.now(tz=UTC)
        reg.updated_by = actor.id

        # Apply changes to the actual attendance record
        record = await self.repo.get_record_by_id(reg.attendance_record_id, school_id)
        if record and not record.is_locked:
            if reg.requested_check_in:
                record.check_in_time = reg.requested_check_in
            if reg.requested_check_out:
                record.check_out_time = reg.requested_check_out
            if reg.requested_status:
                record.status = reg.requested_status
            record.source = AttendanceSource.MANUAL
            record.updated_by = actor.id

        await self.db.flush()
        await self.audit.log_action(
            module="staff_attendance",
            action="regularization.approve",
            entity_name="AttendanceRegularization",
            entity_id=reg.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return reg

    async def reject_regularization(
        self,
        reg_id: uuid.UUID,
        school_id: uuid.UUID,
        data: RegularizationApproveReject,
        actor: User,
    ) -> AttendanceRegularization:
        reg = await self.repo.get_regularization_by_id(reg_id, school_id)
        if not reg:
            raise AttendanceNotFoundException("Regularization request not found.")
        if reg.approval_status != RegularizationStatus.PENDING:
            raise InvalidAttendanceDataException(
                "Only PENDING regularizations can be rejected."
            )

        reg.approval_status = RegularizationStatus.REJECTED
        reg.approver_id = actor.id
        reg.approval_remarks = data.remarks
        reg.approved_at = datetime.now(tz=UTC)
        reg.updated_by = actor.id

        await self.db.flush()
        await self.audit.log_action(
            module="staff_attendance",
            action="regularization.reject",
            entity_name="AttendanceRegularization",
            entity_id=reg.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return reg

    async def list_regularizations(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        status: RegularizationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AttendanceRegularization]:
        return await self.repo.list_regularizations(
            school_id, employee_id, status, skip, limit
        )

    # -----------------------------------------------------------------------
    # Devices
    # -----------------------------------------------------------------------

    async def create_device(
        self, school_id: uuid.UUID, data: AttendanceDeviceCreate, actor: User
    ) -> AttendanceDevice:
        if data.serial_number:
            existing = await self.repo.get_device_by_serial(
                data.serial_number, school_id
            )
            if existing:
                raise InvalidAttendanceDataException(
                    f"Device with serial '{data.serial_number}' already registered."
                )

        device = AttendanceDevice(
            school_id=school_id,
            device_name=data.device_name,
            device_type=data.device_type,
            serial_number=data.serial_number,
            ip_address=data.ip_address,
            location=data.location,
            notes=data.notes,
            created_by=actor.id,
        )
        await self.repo.create_device(device)
        await self.db.flush()
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance_device.create",
            entity_name="AttendanceDevice",
            entity_id=device.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return device

    async def get_device(
        self, device_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceDevice:
        device = await self.repo.get_device_by_id(device_id, school_id)
        if not device:
            raise AttendanceNotFoundException("Device not found.")
        return device

    async def list_devices(
        self, school_id: uuid.UUID, status: DeviceStatus | None = None
    ) -> list[AttendanceDevice]:
        return await self.repo.list_devices(school_id, status)

    async def update_device(
        self,
        device_id: uuid.UUID,
        school_id: uuid.UUID,
        data: AttendanceDeviceUpdate,
        actor: User,
    ) -> AttendanceDevice:
        device = await self.get_device(device_id, school_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(device, field, value)
        device.updated_by = actor.id
        await self.db.flush()
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance_device.update",
            entity_name="AttendanceDevice",
            entity_id=device.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return device

    # -----------------------------------------------------------------------
    # Attendance Logs
    # -----------------------------------------------------------------------

    async def create_log(
        self,
        school_id: uuid.UUID,
        data: AttendanceLogCreate,
        actor: User,
    ) -> AttendanceLog:
        log = AttendanceLog(
            school_id=school_id,
            employee_id=data.employee_id,
            device_id=data.device_id,
            log_timestamp=data.log_timestamp,
            source=data.source,
            raw_data=data.raw_data,
            notes=data.notes,
            created_by=actor.id,
        )
        await self.repo.create_log(log)
        await self.db.flush()
        await self.audit.log_action(
            module="staff_attendance",
            action="attendance_log.create",
            entity_name="AttendanceLog",
            entity_id=log.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return log

    async def list_logs(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        is_processed: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AttendanceLog]:
        return await self.repo.list_logs(
            school_id, employee_id, device_id, is_processed, skip, limit
        )

    async def process_biometric_logs(self, school_id: uuid.UUID, actor: User) -> int:
        """
        Processes raw unprocessed attendance logs into AttendanceRecord rows.
        Returns the count of records created/updated.
        """
        logs = await self.repo.get_unprocessed_logs(school_id)
        processed_count = 0
        for log in logs:
            try:
                log_date = log.log_timestamp.date()
                existing = await self.repo.get_record_by_employee_date(
                    log.employee_id, log_date, school_id
                )
                if existing:
                    # Update check-out time if we already have a check-in
                    if existing.check_in_time and not existing.check_out_time:
                        existing.check_out_time = log.log_timestamp
                        existing.updated_by = actor.id
                else:
                    record = AttendanceRecord(
                        school_id=school_id,
                        employee_id=log.employee_id,
                        attendance_date=log_date,
                        check_in_time=log.log_timestamp,
                        status=AttendanceStatus.PRESENT,
                        source=AttendanceSource.BIOMETRIC,
                        created_by=actor.id,
                    )
                    await self.repo.create_record(record)
                    log.is_processed = True
                    log.processed_record_id = record.id
                    processed_count += 1
            except Exception as exc:
                logger.warning("Failed to process attendance log %s: %s", log.id, exc)
        if processed_count:
            await self.db.flush()
        return processed_count
