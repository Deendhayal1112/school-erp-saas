import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leave.enums import (
    LeaveRequestStatus,
)
from app.modules.leave.models import (
    HolidayCalendar,
    LeaveBalance,
    LeavePolicy,
    LeaveRequest,
    LeaveType,
)


class LeaveRepository:
    """
    Repository class encapsulating database query operations for all Leave module entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 1. LeaveType Queries
    async def create_leave_type(self, lt: LeaveType) -> LeaveType:
        self.session.add(lt)
        return lt

    async def get_leave_type_by_id(
        self, lt_id: uuid.UUID, school_id: uuid.UUID
    ) -> LeaveType | None:
        stmt = select(LeaveType).where(
            LeaveType.id == lt_id,
            LeaveType.school_id == school_id,
            LeaveType.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_leave_type_by_code(
        self, code: str, school_id: uuid.UUID
    ) -> LeaveType | None:
        stmt = select(LeaveType).where(
            LeaveType.leave_code == code,
            LeaveType.school_id == school_id,
            LeaveType.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_leave_types(self, school_id: uuid.UUID) -> list[LeaveType]:
        stmt = (
            select(LeaveType)
            .where(LeaveType.school_id == school_id, LeaveType.is_deleted == False)
            .order_by(LeaveType.leave_name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # 2. LeavePolicy Queries
    async def create_leave_policy(self, lp: LeavePolicy) -> LeavePolicy:
        self.session.add(lp)
        return lp

    async def get_leave_policy_by_id(
        self, lp_id: uuid.UUID, school_id: uuid.UUID
    ) -> LeavePolicy | None:
        stmt = select(LeavePolicy).where(
            LeavePolicy.id == lp_id,
            LeavePolicy.school_id == school_id,
            LeavePolicy.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_leave_policies(
        self,
        school_id: uuid.UUID,
        leave_type_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        employee_type: str | None = None,
    ) -> list[LeavePolicy]:
        stmt = select(LeavePolicy).where(
            LeavePolicy.school_id == school_id, LeavePolicy.is_deleted == False
        )
        if leave_type_id:
            stmt = stmt.where(LeavePolicy.leave_type_id == leave_type_id)
        if department_id:
            stmt = stmt.where(LeavePolicy.department_id == department_id)
        if designation_id:
            stmt = stmt.where(LeavePolicy.designation_id == designation_id)
        if employee_type:
            stmt = stmt.where(LeavePolicy.employee_type == employee_type)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # 3. LeaveBalance Queries
    async def create_leave_balance(self, lb: LeaveBalance) -> LeaveBalance:
        self.session.add(lb)
        return lb

    async def get_leave_balance(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        year: int,
    ) -> LeaveBalance | None:
        stmt = select(LeaveBalance).where(
            LeaveBalance.school_id == school_id,
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == year,
            LeaveBalance.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_leave_balances(
        self, school_id: uuid.UUID, employee_id: uuid.UUID, year: int
    ) -> list[LeaveBalance]:
        stmt = select(LeaveBalance).where(
            LeaveBalance.school_id == school_id,
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
            LeaveBalance.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # 4. LeaveRequest Queries
    async def create_leave_request(self, lr: LeaveRequest) -> LeaveRequest:
        self.session.add(lr)
        return lr

    async def get_leave_request_by_id(
        self, lr_id: uuid.UUID, school_id: uuid.UUID
    ) -> LeaveRequest | None:
        stmt = select(LeaveRequest).where(
            LeaveRequest.id == lr_id,
            LeaveRequest.school_id == school_id,
            LeaveRequest.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_leave_requests(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        leave_type_id: uuid.UUID | None = None,
        status: LeaveRequestStatus | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[LeaveRequest], int]:
        stmt = select(LeaveRequest).where(
            LeaveRequest.school_id == school_id, LeaveRequest.is_deleted == False
        )
        if employee_id:
            stmt = stmt.where(LeaveRequest.employee_id == employee_id)
        if leave_type_id:
            stmt = stmt.where(LeaveRequest.leave_type_id == leave_type_id)
        if status:
            stmt = stmt.where(LeaveRequest.status == status)
        if start_date:
            stmt = stmt.where(LeaveRequest.start_date >= start_date)
        if end_date:
            stmt = stmt.where(LeaveRequest.end_date <= end_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(LeaveRequest.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def has_overlapping_request(
        self,
        employee_id: uuid.UUID,
        start_date: date,
        end_date: date,
        exclude_request_id: uuid.UUID | None = None,
    ) -> bool:
        """Checks if a non-rejected, non-cancelled leave request already covers these dates."""
        stmt = select(func.count(LeaveRequest.id)).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.is_deleted == False,
            LeaveRequest.status.in_(
                [LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]
            ),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        if exclude_request_id:
            stmt = stmt.where(LeaveRequest.id != exclude_request_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    # 5. HolidayCalendar Queries
    async def create_holiday(self, hc: HolidayCalendar) -> HolidayCalendar:
        self.session.add(hc)
        return hc

    async def get_holiday_by_id(
        self, hc_id: uuid.UUID, school_id: uuid.UUID
    ) -> HolidayCalendar | None:
        stmt = select(HolidayCalendar).where(
            HolidayCalendar.id == hc_id,
            HolidayCalendar.school_id == school_id,
            HolidayCalendar.is_active == True,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_holiday_by_date(
        self, d: date, school_id: uuid.UUID
    ) -> HolidayCalendar | None:
        stmt = select(HolidayCalendar).where(
            HolidayCalendar.holiday_date == d,
            HolidayCalendar.school_id == school_id,
            HolidayCalendar.is_active == True,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_holidays(
        self,
        school_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[HolidayCalendar]:
        stmt = select(HolidayCalendar).where(
            HolidayCalendar.school_id == school_id,
            HolidayCalendar.is_active == True,
        )
        if start_date:
            stmt = stmt.where(HolidayCalendar.holiday_date >= start_date)
        if end_date:
            stmt = stmt.where(HolidayCalendar.holiday_date <= end_date)

        stmt = stmt.order_by(HolidayCalendar.holiday_date.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_holidays_in_range(
        self, school_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[date]:
        """Gets holiday dates occurring inside the given range."""
        stmt = select(HolidayCalendar.holiday_date).where(
            HolidayCalendar.school_id == school_id,
            HolidayCalendar.holiday_date >= start_date,
            HolidayCalendar.holiday_date <= end_date,
            HolidayCalendar.is_active == True,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
