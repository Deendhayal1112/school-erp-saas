import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employee.enums import EmployeeType, EmploymentStatus
from app.modules.employee.models import Employee


class EmployeeRepository:
    """
    Repository class encapsulating database query operations for Employee entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, emp: Employee) -> Employee:
        self.session.add(emp)
        return emp

    async def update(self, emp: Employee) -> Employee:
        self.session.add(emp)
        return emp

    async def delete(self, emp: Employee) -> Employee:
        """Applies soft-delete by setting is_deleted=True."""
        emp.is_deleted = True
        emp.deleted_at = func.now()
        self.session.add(emp)
        return emp

    async def restore(self, emp: Employee) -> Employee:
        """Restores a soft-deleted employee."""
        emp.is_deleted = False
        emp.deleted_at = None
        self.session.add(emp)
        return emp

    async def get_by_id(
        self, emp_id: uuid.UUID, include_deleted: bool = False
    ) -> Employee | None:
        stmt = select(Employee).where(Employee.id == emp_id)
        if not include_deleted:
            stmt = stmt.where(Employee.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Employee) else None

    async def get_by_employee_number(
        self, school_id: uuid.UUID, emp_num: str
    ) -> Employee | None:
        stmt = select(Employee).where(
            Employee.school_id == school_id,
            func.lower(Employee.employee_number) == emp_num.lower(),
            Employee.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Employee) else None

    async def get_by_email(self, school_id: uuid.UUID, email: str) -> Employee | None:
        stmt = select(Employee).where(
            Employee.school_id == school_id,
            func.lower(Employee.email) == email.lower(),
            Employee.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Employee) else None

    async def get_by_department(self, dept_id: uuid.UUID) -> list[Employee]:
        stmt = (
            select(Employee)
            .where(
                Employee.department_id == dept_id,
                Employee.is_deleted == False,
            )
            .order_by(Employee.employee_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_designation(self, desg_id: uuid.UUID) -> list[Employee]:
        stmt = (
            select(Employee)
            .where(
                Employee.designation_id == desg_id,
                Employee.is_deleted == False,
            )
            .order_by(Employee.employee_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists_number(
        self, school_id: uuid.UUID, emp_num: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Employee.id)).where(
            Employee.school_id == school_id,
            func.lower(Employee.employee_number) == emp_num.lower(),
            Employee.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Employee.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_email(
        self, school_id: uuid.UUID, email: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Employee.id)).where(
            Employee.school_id == school_id,
            func.lower(Employee.email) == email.lower(),
            Employee.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Employee.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_phone(
        self, school_id: uuid.UUID, phone: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Employee.id)).where(
            Employee.school_id == school_id,
            func.lower(Employee.phone) == phone.lower(),
            Employee.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Employee.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        employee_type: EmployeeType | None = None,
        employment_status: EmploymentStatus | None = None,
        gender: str | None = None,
        is_active: bool | None = None,
        sort_by: str | None = "employee_number",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Employee], int]:
        stmt = select(Employee).where(
            Employee.school_id == school_id,
            Employee.is_deleted == False,
        )

        # Filters
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)
        if designation_id:
            stmt = stmt.where(Employee.designation_id == designation_id)
        if employee_type:
            stmt = stmt.where(Employee.employee_type == employee_type)
        if employment_status:
            stmt = stmt.where(Employee.employment_status == employment_status)
        if gender:
            stmt = stmt.where(Employee.gender.ilike(gender))
        if is_active is not None:
            stmt = stmt.where(Employee.is_active == is_active)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        col: Any = Employee.employee_number
        if sort_by == "first_name":
            col = Employee.first_name
        elif sort_by == "joining_date":
            col = Employee.joining_date
        elif sort_by == "created_at":
            col = Employee.created_at

        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
