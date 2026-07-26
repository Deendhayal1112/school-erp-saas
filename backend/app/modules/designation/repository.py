import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.designation.enums import DesignationStatus
from app.modules.designation.models import Designation


class DesignationRepository:
    """
    Repository class encapsulating database query operations for Designation entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, des: Designation) -> Designation:
        self.session.add(des)
        return des

    async def update(self, des: Designation) -> Designation:
        self.session.add(des)
        return des

    async def delete(self, des: Designation) -> Designation:
        """Applies soft-delete by setting is_deleted=True."""
        des.is_deleted = True
        des.deleted_at = func.now()
        self.session.add(des)
        return des

    async def restore(self, des: Designation) -> Designation:
        """Restores a soft-deleted designation."""
        des.is_deleted = False
        des.deleted_at = None
        self.session.add(des)
        return des

    async def get_by_id(
        self, des_id: uuid.UUID, include_deleted: bool = False
    ) -> Designation | None:
        stmt = select(Designation).where(Designation.id == des_id)
        if not include_deleted:
            stmt = stmt.where(Designation.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Designation) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> Designation | None:
        stmt = select(Designation).where(
            Designation.school_id == school_id,
            func.lower(Designation.designation_code) == code.lower(),
            Designation.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Designation) else None

    async def get_by_name(self, dept_id: uuid.UUID, name: str) -> Designation | None:
        stmt = select(Designation).where(
            Designation.department_id == dept_id,
            func.lower(Designation.designation_name) == name.lower(),
            Designation.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Designation) else None

    async def get_by_department(self, dept_id: uuid.UUID) -> list[Designation]:
        stmt = (
            select(Designation)
            .where(
                Designation.department_id == dept_id,
                Designation.is_deleted == False,
            )
            .order_by(Designation.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists_code(
        self, school_id: uuid.UUID, code: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Designation.id)).where(
            Designation.school_id == school_id,
            func.lower(Designation.designation_code) == code.lower(),
            Designation.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Designation.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def exists_name(
        self, dept_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        stmt = select(func.count(Designation.id)).where(
            Designation.department_id == dept_id,
            func.lower(Designation.designation_name) == name.lower(),
            Designation.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Designation.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        is_teaching: bool | None = None,
        is_management: bool | None = None,
        employment_category: str | None = None,
        status: DesignationStatus | None = None,
        job_level: str | None = None,
        grade: str | None = None,
        sort_by: str | None = "designation_name",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Designation], int]:
        stmt = select(Designation).where(
            Designation.school_id == school_id,
            Designation.is_deleted == False,
        )

        # Filters
        if department_id:
            stmt = stmt.where(Designation.department_id == department_id)
        if is_teaching is not None:
            stmt = stmt.where(Designation.is_teaching == is_teaching)
        if is_management is not None:
            stmt = stmt.where(Designation.is_management == is_management)
        if employment_category:
            stmt = stmt.where(
                Designation.employment_category.ilike(f"%{employment_category}%")
            )
        if status:
            stmt = stmt.where(Designation.status == status)
        if job_level:
            stmt = stmt.where(Designation.job_level == job_level)
        if grade:
            stmt = stmt.where(Designation.grade == grade)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        col: Any = Designation.designation_name
        if sort_by == "created_at":
            col = Designation.created_at
        elif sort_by == "display_order":
            col = Designation.display_order
        elif sort_by == "salary_band":
            col = Designation.salary_band

        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
