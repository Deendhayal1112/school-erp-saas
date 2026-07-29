import builtins
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.qualification.enums import QualificationStatus, QualificationType
from app.modules.qualification.models import Qualification


class QualificationRepository:
    """
    Repository class encapsulating database query operations for Qualification entities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, q: Qualification) -> Qualification:
        self.session.add(q)
        return q

    async def update(self, q: Qualification) -> Qualification:
        self.session.add(q)
        return q

    async def delete(self, q: Qualification) -> Qualification:
        """Applies soft-delete by setting is_deleted=True."""
        q.is_deleted = True
        q.deleted_at = func.now()
        self.session.add(q)
        return q

    async def restore(self, q: Qualification) -> Qualification:
        """Restores a soft-deleted qualification."""
        q.is_deleted = False
        q.deleted_at = None
        self.session.add(q)
        return q

    async def get_by_id(
        self, q_id: uuid.UUID, include_deleted: bool = False
    ) -> Qualification | None:
        stmt = select(Qualification).where(Qualification.id == q_id)
        if not include_deleted:
            stmt = stmt.where(Qualification.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_employee(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> list[Qualification]:
        stmt = select(Qualification).where(
            Qualification.school_id == school_id,
            Qualification.employee_id == employee_id,
        )
        if not include_deleted:
            stmt = stmt.where(Qualification.is_deleted == False)
        stmt = stmt.order_by(
            Qualification.passing_year.desc(), Qualification.created_at.desc()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list(
        self,
        school_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        qualification_type: QualificationType | None = None,
        institution_name: str | None = None,
        is_verified: bool | None = None,
        is_highest_qualification: bool | None = None,
        passing_year: int | None = None,
        status: QualificationStatus | None = None,
        sort_by: str | None = "passing_year",
        sort_dir: str | None = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Qualification], int]:
        stmt = select(Qualification).where(
            Qualification.school_id == school_id,
            Qualification.is_deleted == False,
        )

        if employee_id:
            stmt = stmt.where(Qualification.employee_id == employee_id)
        if qualification_type:
            stmt = stmt.where(Qualification.qualification_type == qualification_type)
        if institution_name:
            stmt = stmt.where(
                Qualification.institution_name.ilike(f"%{institution_name}%")
            )
        if is_verified is not None:
            stmt = stmt.where(Qualification.is_verified == is_verified)
        if is_highest_qualification is not None:
            stmt = stmt.where(
                Qualification.is_highest_qualification == is_highest_qualification
            )
        if passing_year is not None:
            stmt = stmt.where(Qualification.passing_year == passing_year)
        if status:
            stmt = stmt.where(Qualification.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        col: Any = Qualification.passing_year
        if sort_by == "qualification_name":
            col = Qualification.qualification_name
        elif sort_by == "created_at":
            col = Qualification.created_at

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
    ) -> tuple[builtins.list[Qualification], int]:
        stmt = select(Qualification).where(
            Qualification.school_id == school_id,
            Qualification.is_deleted == False,
            (
                Qualification.qualification_name.ilike(f"%{query}%")
                | Qualification.degree.ilike(f"%{query}%")
                | Qualification.specialization.ilike(f"%{query}%")
                | Qualification.institution_name.ilike(f"%{query}%")
            ),
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            stmt.order_by(Qualification.qualification_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def activate(self, q: Qualification) -> Qualification:
        q.is_active = True
        self.session.add(q)
        return q

    async def deactivate(self, q: Qualification) -> Qualification:
        q.is_active = False
        self.session.add(q)
        return q

    async def lock(self, q: Qualification) -> Qualification:
        q.is_locked = True
        self.session.add(q)
        return q

    async def unlock(self, q: Qualification) -> Qualification:
        q.is_locked = False
        self.session.add(q)
        return q

    async def archive(self, q: Qualification) -> Qualification:
        q.status = QualificationStatus.ARCHIVED
        q.is_active = False
        self.session.add(q)
        return q

    async def verify(self, q: Qualification, user_id: uuid.UUID) -> Qualification:
        q.is_verified = True
        q.verification_date = datetime.now()
        q.verification_by = user_id
        self.session.add(q)
        return q

    async def exists(self, q_id: uuid.UUID) -> bool:
        stmt = select(func.count(Qualification.id)).where(
            Qualification.id == q_id,
            Qualification.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def reset_highest_qualification_except(
        self, employee_id: uuid.UUID, except_q_id: uuid.UUID | None = None
    ) -> None:
        """Sets is_highest_qualification to False for all other employee qualifications."""
        stmt = select(Qualification).where(
            Qualification.employee_id == employee_id,
            Qualification.is_highest_qualification == True,
            Qualification.is_deleted == False,
        )
        if except_q_id:
            stmt = stmt.where(Qualification.id != except_q_id)
        result = await self.session.execute(stmt)
        for q in result.scalars().all():
            q.is_highest_qualification = False
            self.session.add(q)
