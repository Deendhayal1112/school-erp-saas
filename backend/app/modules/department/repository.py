import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.department.enums import DepartmentStatus
from app.modules.department.models import Department


class DepartmentRepository:
    """
    Repository class encapsulating database query operations for Department entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, dept: Department) -> Department:
        self.session.add(dept)
        return dept

    async def update(self, dept: Department) -> Department:
        self.session.add(dept)
        return dept

    async def delete(self, dept: Department) -> Department:
        """Applies soft-delete by setting is_deleted=True."""
        dept.is_deleted = True
        dept.deleted_at = func.now()
        self.session.add(dept)
        return dept

    async def restore(self, dept: Department) -> Department:
        """Restores a soft-deleted department."""
        dept.is_deleted = False
        dept.deleted_at = None
        self.session.add(dept)
        return dept

    async def get_by_id(
        self, dept_id: uuid.UUID, include_deleted: bool = False
    ) -> Department | None:
        stmt = select(Department).where(Department.id == dept_id)
        if not include_deleted:
            stmt = stmt.where(Department.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Department) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> Department | None:
        stmt = select(Department).where(
            Department.school_id == school_id,
            func.lower(Department.department_code) == code.lower(),
            Department.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Department) else None

    async def get_by_name(self, school_id: uuid.UUID, name: str) -> Department | None:
        stmt = select(Department).where(
            Department.school_id == school_id,
            func.lower(Department.department_name) == name.lower(),
            Department.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Department) else None

    async def exists_code(
        self, school_id: uuid.UUID, code: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Department.id)).where(
            Department.school_id == school_id,
            func.lower(Department.department_code) == code.lower(),
            Department.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Department.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_name(
        self, school_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Department.id)).where(
            Department.school_id == school_id,
            func.lower(Department.department_name) == name.lower(),
            Department.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Department.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        name: str | None = None,
        code: str | None = None,
        is_academic: bool | None = None,
        status: DepartmentStatus | None = None,
        location: str | None = None,
        building: str | None = None,
        sort_by: str | None = "department_name",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Department], int]:
        stmt = select(Department).where(
            Department.school_id == school_id,
            Department.is_deleted == False,
        )

        # Filters
        if name:
            stmt = stmt.where(Department.department_name.ilike(f"%{name}%"))
        if code:
            stmt = stmt.where(Department.department_code.ilike(f"%{code}%"))
        if is_academic is not None:
            stmt = stmt.where(Department.is_academic == is_academic)
        if status:
            stmt = stmt.where(Department.status == status)
        if location:
            stmt = stmt.where(Department.location.ilike(f"%{location}%"))
        if building:
            stmt = stmt.where(Department.building.ilike(f"%{building}%"))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        col: Any = Department.department_name
        if sort_by == "created_at":
            col = Department.created_at
        elif sort_by == "display_order":
            col = Department.display_order

        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
