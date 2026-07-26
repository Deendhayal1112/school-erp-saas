import uuid
from typing import Any

from sqlalchemy import func, select

from app.modules.academic_settings.enums import AcademicSettingsStatus
from app.modules.academic_settings.models import AcademicSettings


class AcademicSettingsRepository:
    """
    Repository class encapsulating database query operations for AcademicSettings.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, settings: AcademicSettings) -> AcademicSettings:
        self.session.add(settings)
        return settings

    async def update(self, settings: AcademicSettings) -> AcademicSettings:
        self.session.add(settings)
        return settings

    async def get_by_id(self, settings_id: uuid.UUID) -> AcademicSettings | None:
        stmt = select(AcademicSettings).where(
            AcademicSettings.id == settings_id,
            AcademicSettings.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicSettings) else None

    async def get_active(self, school_id: uuid.UUID) -> AcademicSettings | None:
        """Retrieves the single active academic settings configuration for a school."""
        stmt = select(AcademicSettings).where(
            AcademicSettings.school_id == school_id,
            AcademicSettings.status == AcademicSettingsStatus.ACTIVE,
            AcademicSettings.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicSettings) else None

    async def get_by_year(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> AcademicSettings | None:
        """Retrieves settings mapping for a specific academic year."""
        stmt = select(AcademicSettings).where(
            AcademicSettings.school_id == school_id,
            AcademicSettings.academic_year_id == academic_year_id,
            AcademicSettings.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, AcademicSettings) else None

    async def exists(self, school_id: uuid.UUID, academic_year_id: uuid.UUID) -> bool:
        stmt = select(func.count(AcademicSettings.id)).where(
            AcademicSettings.school_id == school_id,
            AcademicSettings.academic_year_id == academic_year_id,
            AcademicSettings.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        status: AcademicSettingsStatus | None = None,
        sort_by: str | None = "created_at",
        sort_dir: str | None = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AcademicSettings], int]:
        stmt = select(AcademicSettings).where(
            AcademicSettings.school_id == school_id,
            AcademicSettings.is_deleted == False,
        )

        if academic_year_id:
            stmt = stmt.where(AcademicSettings.academic_year_id == academic_year_id)
        if status:
            stmt = stmt.where(AcademicSettings.status == status)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        col: Any = AcademicSettings.created_at
        if sort_by == "updated_at":
            col = AcademicSettings.updated_at

        if sort_dir == "asc":
            stmt = stmt.order_by(col.asc())
        else:
            stmt = stmt.order_by(col.desc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
