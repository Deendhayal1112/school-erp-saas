import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear


class AcademicYearRepository:
    """
    Repository class encapsulating database query operations for Academic Years.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, ay: AcademicYear) -> AcademicYear:
        self.session.add(ay)
        return ay

    async def update(self, ay: AcademicYear) -> AcademicYear:
        self.session.add(ay)
        return ay

    async def delete(self, ay_id: uuid.UUID) -> bool:
        ay = await self.get_by_id(ay_id, include_deleted=True)
        if ay and not ay.is_deleted:
            ay.is_deleted = True
            ay.deleted_at = datetime.now(UTC)
            self.session.add(ay)
            return True
        return False

    async def restore(self, ay_id: uuid.UUID) -> bool:
        ay = await self.get_by_id(ay_id, include_deleted=True)
        if ay and ay.is_deleted:
            ay.is_deleted = False
            ay.deleted_at = None
            self.session.add(ay)
            return True
        return False

    async def get_by_id(
        self, ay_id: uuid.UUID, include_deleted: bool = False
    ) -> AcademicYear | None:
        stmt = select(AcademicYear).where(AcademicYear.id == ay_id)
        if not include_deleted:
            stmt = stmt.where(AcademicYear.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicYear) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> AcademicYear | None:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            AcademicYear.code == code,
            AcademicYear.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicYear) else None

    async def get_by_name(self, school_id: uuid.UUID, name: str) -> AcademicYear | None:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            AcademicYear.name == name,
            AcademicYear.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicYear) else None

    async def get_active(self, school_id: uuid.UUID) -> AcademicYear | None:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            AcademicYear.status == AcademicYearStatus.ACTIVE,
            AcademicYear.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicYear) else None

    async def get_default(self, school_id: uuid.UUID) -> AcademicYear | None:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            AcademicYear.is_default == True,
            AcademicYear.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicYear) else None

    async def check_overlapping(
        self,
        school_id: uuid.UUID,
        start_date: date,
        end_date: date,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Returns True if there is an overlapping academic year within the same school.
        Overlap criteria: (StartA <= EndB) and (EndA >= StartB)
        """
        stmt = select(func.count(AcademicYear.id)).where(
            AcademicYear.school_id == school_id,
            AcademicYear.is_deleted == False,
            AcademicYear.start_date <= end_date,
            AcademicYear.end_date >= start_date,
        )
        if exclude_id:
            stmt = stmt.where(AcademicYear.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_other_active_years(
        self, school_id: uuid.UUID, exclude_id: uuid.UUID
    ) -> list[AcademicYear]:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            AcademicYear.id != exclude_id,
            AcademicYear.status == AcademicYearStatus.ACTIVE,
            AcademicYear.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_other_default_years(
        self, school_id: uuid.UUID, exclude_id: uuid.UUID
    ) -> list[AcademicYear]:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            AcademicYear.id != exclude_id,
            AcademicYear.is_default == True,
            AcademicYear.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self,
        school_id: uuid.UUID,
        name: str | None = None,
        code: str | None = None,
        status: AcademicYearStatus | None = None,
        search: str | None = None,
    ) -> list[AcademicYear]:
        stmt = select(AcademicYear).where(
            AcademicYear.school_id == school_id, AcademicYear.is_deleted == False
        )

        if name:
            stmt = stmt.where(AcademicYear.name.ilike(f"%{name}%"))
        if code:
            stmt = stmt.where(AcademicYear.code.ilike(f"%{code}%"))
        if status:
            stmt = stmt.where(AcademicYear.status == status)
        if search:
            stmt = stmt.where(
                or_(
                    AcademicYear.name.ilike(f"%{search}%"),
                    AcademicYear.code.ilike(f"%{search}%"),
                )
            )

        stmt = stmt.order_by(AcademicYear.start_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
