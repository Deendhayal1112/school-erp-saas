import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff_attendance.enums import (
    AttendanceStatus,
    DeviceStatus,
    RegularizationStatus,
    ShiftStatus,
)
from app.modules.staff_attendance.models import (
    AttendanceDevice,
    AttendanceLog,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceRegularization,
    AttendanceShift,
)


class AttendanceRepository:
    """
    Repository class encapsulating all database query operations for the
    Staff Attendance module, maintaining strict tenant isolation via school_id.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -----------------------------------------------------------------------
    # AttendanceShift
    # -----------------------------------------------------------------------

    async def create_shift(self, shift: AttendanceShift) -> AttendanceShift:
        self.session.add(shift)
        return shift

    async def get_shift_by_id(
        self, shift_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceShift | None:
        stmt = select(AttendanceShift).where(
            AttendanceShift.id == shift_id,
            AttendanceShift.school_id == school_id,
            AttendanceShift.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_shift_by_code(
        self, code: str, school_id: uuid.UUID
    ) -> AttendanceShift | None:
        stmt = select(AttendanceShift).where(
            AttendanceShift.shift_code == code,
            AttendanceShift.school_id == school_id,
            AttendanceShift.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_shifts(
        self,
        school_id: uuid.UUID,
        active_only: bool = False,
    ) -> list[AttendanceShift]:
        stmt = select(AttendanceShift).where(
            AttendanceShift.school_id == school_id,
            AttendanceShift.is_deleted == False,
        )
        if active_only:
            stmt = stmt.where(AttendanceShift.status == ShiftStatus.ACTIVE)
        stmt = stmt.order_by(AttendanceShift.shift_name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def archive_shift(self, shift: AttendanceShift) -> AttendanceShift:
        shift.status = ShiftStatus.ARCHIVED
        return shift

    # -----------------------------------------------------------------------
    # AttendancePolicy
    # -----------------------------------------------------------------------

    async def create_policy(self, policy: AttendancePolicy) -> AttendancePolicy:
        self.session.add(policy)
        return policy

    async def get_policy_by_id(
        self, policy_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendancePolicy | None:
        stmt = select(AttendancePolicy).where(
            AttendancePolicy.id == policy_id,
            AttendancePolicy.school_id == school_id,
            AttendancePolicy.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_policy(self, school_id: uuid.UUID) -> AttendancePolicy | None:
        stmt = select(AttendancePolicy).where(
            AttendancePolicy.school_id == school_id,
            AttendancePolicy.is_default == True,
            AttendancePolicy.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_policies(self, school_id: uuid.UUID) -> list[AttendancePolicy]:
        stmt = (
            select(AttendancePolicy)
            .where(
                AttendancePolicy.school_id == school_id,
                AttendancePolicy.is_deleted == False,
            )
            .order_by(AttendancePolicy.policy_name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # AttendanceRecord
    # -----------------------------------------------------------------------

    async def create_record(self, record: AttendanceRecord) -> AttendanceRecord:
        self.session.add(record)
        return record

    async def get_record_by_id(
        self, record_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceRecord | None:
        stmt = select(AttendanceRecord).where(
            AttendanceRecord.id == record_id,
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_record_by_employee_date(
        self,
        employee_id: uuid.UUID,
        attendance_date: date,
        school_id: uuid.UUID,
    ) -> AttendanceRecord | None:
        stmt = select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.attendance_date == attendance_date,
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_records(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        shift_id: uuid.UUID | None = None,
        status: AttendanceStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AttendanceRecord]:
        stmt = select(AttendanceRecord).where(
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.is_deleted == False,
        )
        if employee_id:
            stmt = stmt.where(AttendanceRecord.employee_id == employee_id)
        if shift_id:
            stmt = stmt.where(AttendanceRecord.shift_id == shift_id)
        if status:
            stmt = stmt.where(AttendanceRecord.status == status)
        if date_from:
            stmt = stmt.where(AttendanceRecord.attendance_date >= date_from)
        if date_to:
            stmt = stmt.where(AttendanceRecord.attendance_date <= date_to)
        stmt = (
            stmt.order_by(AttendanceRecord.attendance_date.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_records_by_status_month(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        month: int,
        year: int,
        status: AttendanceStatus,
    ) -> int:
        stmt = select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.status == status,
            func.extract("month", AttendanceRecord.attendance_date) == month,
            func.extract("year", AttendanceRecord.attendance_date) == year,
            AttendanceRecord.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_monthly_records(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        month: int,
        year: int,
    ) -> list[AttendanceRecord]:
        stmt = (
            select(AttendanceRecord)
            .where(
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.employee_id == employee_id,
                func.extract("month", AttendanceRecord.attendance_date) == month,
                func.extract("year", AttendanceRecord.attendance_date) == year,
                AttendanceRecord.is_deleted == False,
            )
            .order_by(AttendanceRecord.attendance_date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # AttendanceRegularization
    # -----------------------------------------------------------------------

    async def create_regularization(
        self, reg: AttendanceRegularization
    ) -> AttendanceRegularization:
        self.session.add(reg)
        return reg

    async def get_regularization_by_id(
        self, reg_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceRegularization | None:
        stmt = select(AttendanceRegularization).where(
            AttendanceRegularization.id == reg_id,
            AttendanceRegularization.school_id == school_id,
            AttendanceRegularization.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_regularization_for_record(
        self, record_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceRegularization | None:
        stmt = select(AttendanceRegularization).where(
            AttendanceRegularization.attendance_record_id == record_id,
            AttendanceRegularization.approval_status == RegularizationStatus.PENDING,
            AttendanceRegularization.school_id == school_id,
            AttendanceRegularization.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_regularizations(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        status: RegularizationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AttendanceRegularization]:
        stmt = select(AttendanceRegularization).where(
            AttendanceRegularization.school_id == school_id,
            AttendanceRegularization.is_deleted == False,
        )
        if employee_id:
            stmt = stmt.where(AttendanceRegularization.employee_id == employee_id)
        if status:
            stmt = stmt.where(AttendanceRegularization.approval_status == status)
        stmt = (
            stmt.order_by(AttendanceRegularization.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # AttendanceDevice
    # -----------------------------------------------------------------------

    async def create_device(self, device: AttendanceDevice) -> AttendanceDevice:
        self.session.add(device)
        return device

    async def get_device_by_id(
        self, device_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceDevice | None:
        stmt = select(AttendanceDevice).where(
            AttendanceDevice.id == device_id,
            AttendanceDevice.school_id == school_id,
            AttendanceDevice.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_device_by_serial(
        self, serial_number: str, school_id: uuid.UUID
    ) -> AttendanceDevice | None:
        stmt = select(AttendanceDevice).where(
            AttendanceDevice.serial_number == serial_number,
            AttendanceDevice.school_id == school_id,
            AttendanceDevice.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_devices(
        self,
        school_id: uuid.UUID,
        status: DeviceStatus | None = None,
    ) -> list[AttendanceDevice]:
        stmt = select(AttendanceDevice).where(
            AttendanceDevice.school_id == school_id,
            AttendanceDevice.is_deleted == False,
        )
        if status:
            stmt = stmt.where(AttendanceDevice.status == status)
        stmt = stmt.order_by(AttendanceDevice.device_name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # AttendanceLog
    # -----------------------------------------------------------------------

    async def create_log(self, log: AttendanceLog) -> AttendanceLog:
        self.session.add(log)
        return log

    async def get_log_by_id(
        self, log_id: uuid.UUID, school_id: uuid.UUID
    ) -> AttendanceLog | None:
        stmt = select(AttendanceLog).where(
            AttendanceLog.id == log_id,
            AttendanceLog.school_id == school_id,
            AttendanceLog.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_logs(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        is_processed: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AttendanceLog]:
        stmt = select(AttendanceLog).where(
            AttendanceLog.school_id == school_id,
            AttendanceLog.is_deleted == False,
        )
        if employee_id:
            stmt = stmt.where(AttendanceLog.employee_id == employee_id)
        if device_id:
            stmt = stmt.where(AttendanceLog.device_id == device_id)
        if is_processed is not None:
            stmt = stmt.where(AttendanceLog.is_processed == is_processed)
        stmt = (
            stmt.order_by(AttendanceLog.log_timestamp.desc()).offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unprocessed_logs(
        self, school_id: uuid.UUID, limit: int = 500
    ) -> list[AttendanceLog]:
        stmt = (
            select(AttendanceLog)
            .where(
                AttendanceLog.school_id == school_id,
                AttendanceLog.is_processed == False,
                AttendanceLog.is_deleted == False,
            )
            .order_by(AttendanceLog.log_timestamp.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
