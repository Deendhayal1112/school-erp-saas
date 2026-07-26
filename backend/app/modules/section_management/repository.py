import uuid
from typing import Any

from sqlalchemy import func, select

from app.modules.section_management.enums import SectionStatus
from app.modules.section_management.models import Section


class SectionRepository:
    """
    Repository class encapsulating database query operations for Sections.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, section: Section) -> Section:
        self.session.add(section)
        return section

    async def update(self, section: Section) -> Section:
        self.session.add(section)
        return section

    async def delete(self, section_id: uuid.UUID) -> bool:
        sec = await self.get_by_id(section_id, include_deleted=True)
        if sec and not sec.is_deleted:
            sec.is_deleted = True
            sec.deleted_at = func.now()
            self.session.add(sec)
            return True
        return False

    async def restore(self, section_id: uuid.UUID) -> bool:
        sec = await self.get_by_id(section_id, include_deleted=True)
        if sec and sec.is_deleted:
            sec.is_deleted = False
            sec.deleted_at = None
            self.session.add(sec)
            return True
        return False

    async def get_by_id(
        self, section_id: uuid.UUID, include_deleted: bool = False
    ) -> Section | None:
        stmt = select(Section).where(Section.id == section_id)
        if not include_deleted:
            stmt = stmt.where(Section.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Section) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> Section | None:
        stmt = select(Section).where(
            Section.school_id == school_id,
            Section.code == code,
            Section.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Section) else None

    async def get_by_name(self, class_id: uuid.UUID, name: str) -> Section | None:
        stmt = select(Section).where(
            Section.class_id == class_id,
            Section.name == name,
            Section.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Section) else None

    async def get_by_display_order(
        self, class_id: uuid.UUID, display_order: int
    ) -> Section | None:
        stmt = select(Section).where(
            Section.class_id == class_id,
            Section.display_order == display_order,
            Section.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Section) else None

    async def get_default_section(self, class_id: uuid.UUID) -> Section | None:
        stmt = select(Section).where(
            Section.class_id == class_id,
            Section.is_default == True,
            Section.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Section) else None

    async def list_other_default_sections(
        self, class_id: uuid.UUID, exclude_id: uuid.UUID
    ) -> list[Section]:
        stmt = select(Section).where(
            Section.class_id == class_id,
            Section.id != exclude_id,
            Section.is_default == True,
            Section.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_class(self, class_id: uuid.UUID) -> list[Section]:
        stmt = (
            select(Section)
            .where(
                Section.class_id == class_id,
                Section.is_deleted == False,
            )
            .order_by(Section.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_academic_year(self, academic_year_id: uuid.UUID) -> list[Section]:
        stmt = (
            select(Section)
            .where(
                Section.academic_year_id == academic_year_id,
                Section.is_deleted == False,
            )
            .order_by(Section.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        status: SectionStatus | None = None,
        name: str | None = None,
        code: str | None = None,
        capacity: int | None = None,
        sort_by: str | None = "display_order",
        sort_dir: str | None = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Section], int]:
        stmt = select(Section).where(
            Section.school_id == school_id, Section.is_deleted == False
        )

        if academic_year_id:
            stmt = stmt.where(Section.academic_year_id == academic_year_id)
        if class_id:
            stmt = stmt.where(Section.class_id == class_id)
        if status:
            stmt = stmt.where(Section.status == status)
        if name:
            stmt = stmt.where(Section.name.ilike(f"%{name}%"))
        if code:
            stmt = stmt.where(Section.code.ilike(f"%{code}%"))
        if capacity is not None:
            stmt = stmt.where(Section.capacity == capacity)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        sort_columns = {
            "display_order": Section.display_order,
            "name": Section.name,
            "created_at": Section.created_at,
        }
        col = sort_columns.get(sort_by or "display_order", Section.display_order)
        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
