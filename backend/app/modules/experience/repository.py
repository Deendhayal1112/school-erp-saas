import builtins
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.experience.enums import EmploymentType, ExperienceStatus
from app.modules.experience.models import Experience


class ExperienceRepository:
    """
    Repository class encapsulating database query operations for Experience entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, exp: Experience) -> Experience:
        self.session.add(exp)
        return exp

    async def update(self, exp: Experience) -> Experience:
        self.session.add(exp)
        return exp

    async def delete(self, exp: Experience) -> Experience:
        """Applies soft-delete by setting is_deleted=True."""
        exp.is_deleted = True
        exp.deleted_at = func.now()
        self.session.add(exp)
        return exp

    async def restore(self, exp: Experience) -> Experience:
        """Restores a soft-deleted experience record."""
        exp.is_deleted = False
        exp.deleted_at = None
        self.session.add(exp)
        return exp

    async def get_by_id(
        self, exp_id: uuid.UUID, include_deleted: bool = False
    ) -> Experience | None:
        stmt = select(Experience).where(Experience.id == exp_id)
        if not include_deleted:
            stmt = stmt.where(Experience.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_employee(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> list[Experience]:
        stmt = select(Experience).where(
            Experience.school_id == school_id,
            Experience.employee_id == employee_id,
        )
        if not include_deleted:
            stmt = stmt.where(Experience.is_deleted == False)
        stmt = stmt.order_by(Experience.start_date.desc(), Experience.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        employment_type: EmploymentType | None = None,
        organization_name: str | None = None,
        is_verified: bool | None = None,
        currently_working: bool | None = None,
        status: ExperienceStatus | None = None,
        sort_by: str | None = "start_date",
        sort_dir: str | None = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Experience], int]:
        stmt = select(Experience).where(
            Experience.school_id == school_id,
            Experience.is_deleted == False,
        )

        if employee_id:
            stmt = stmt.where(Experience.employee_id == employee_id)
        if employment_type:
            stmt = stmt.where(Experience.employment_type == employment_type)
        if organization_name:
            stmt = stmt.where(
                Experience.organization_name.ilike(f"%{organization_name}%")
            )
        if is_verified is not None:
            stmt = stmt.where(Experience.is_verified == is_verified)
        if currently_working is not None:
            stmt = stmt.where(Experience.currently_working == currently_working)
        if status:
            stmt = stmt.where(Experience.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        col: Any = Experience.start_date
        if sort_by == "end_date":
            col = Experience.end_date
        elif sort_by == "organization_name":
            col = Experience.organization_name
        elif sort_by == "created_at":
            col = Experience.created_at

        if sort_dir == "asc":
            stmt = stmt.order_by(col.asc())
        else:
            stmt = stmt.order_by(col.desc())

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def search(
        self,
        school_id: uuid.UUID,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[builtins.list[Experience], int]:
        stmt = select(Experience).where(
            Experience.school_id == school_id,
            Experience.is_deleted == False,
            (
                Experience.organization_name.ilike(f"%{query}%")
                | Experience.designation.ilike(f"%{query}%")
                | Experience.department.ilike(f"%{query}%")
            ),
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Experience.start_date.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def activate(self, exp: Experience) -> Experience:
        exp.is_active = True
        self.session.add(exp)
        return exp

    async def deactivate(self, exp: Experience) -> Experience:
        exp.is_active = False
        self.session.add(exp)
        return exp

    async def lock(self, exp: Experience) -> Experience:
        exp.is_locked = True
        self.session.add(exp)
        return exp

    async def unlock(self, exp: Experience) -> Experience:
        exp.is_locked = False
        self.session.add(exp)
        return exp

    async def archive(self, exp: Experience) -> Experience:
        exp.status = ExperienceStatus.ARCHIVED
        exp.is_active = False
        self.session.add(exp)
        return exp

    async def verify(self, exp: Experience, user_id: uuid.UUID) -> Experience:
        exp.is_verified = True
        exp.verification_date = datetime.now()
        exp.verification_by = user_id
        self.session.add(exp)
        return exp

    async def exists(self, exp_id: uuid.UUID) -> bool:
        stmt = select(func.count(Experience.id)).where(
            Experience.id == exp_id,
            Experience.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def get_verified_experiences(
        self, employee_id: uuid.UUID
    ) -> builtins.list[Experience]:
        """Gets all verified, non-deleted experiences for an employee."""
        stmt = select(Experience).where(
            Experience.employee_id == employee_id,
            Experience.is_verified == True,
            Experience.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
