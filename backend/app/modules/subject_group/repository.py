import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.modules.subject_group.enums import SubjectGroupStatus
from app.modules.subject_group.models import SubjectGroup, SubjectGroupMapping


class SubjectGroupRepository:
    """
    Repository class encapsulating database query operations for Subject Groups and Mappings.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, group: SubjectGroup) -> SubjectGroup:
        self.session.add(group)
        return group

    async def update(self, group: SubjectGroup) -> SubjectGroup:
        self.session.add(group)
        return group

    async def delete(self, group_id: uuid.UUID) -> bool:
        group = await self.get_by_id(group_id, include_deleted=True)
        if group and not group.is_deleted:
            group.is_deleted = True
            group.deleted_at = func.now()
            self.session.add(group)
            return True
        return False

    async def restore(self, group_id: uuid.UUID) -> bool:
        group = await self.get_by_id(group_id, include_deleted=True)
        if group and group.is_deleted:
            group.is_deleted = False
            group.deleted_at = None
            self.session.add(group)
            return True
        return False

    async def get_by_id(
        self, group_id: uuid.UUID, include_deleted: bool = False
    ) -> SubjectGroup | None:
        stmt = select(SubjectGroup).where(SubjectGroup.id == group_id)
        if not include_deleted:
            stmt = stmt.where(SubjectGroup.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, SubjectGroup) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> SubjectGroup | None:
        stmt = select(SubjectGroup).where(
            SubjectGroup.school_id == school_id,
            SubjectGroup.group_code == code,
            SubjectGroup.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, SubjectGroup) else None

    async def get_by_name(self, school_id: uuid.UUID, name: str) -> SubjectGroup | None:
        stmt = select(SubjectGroup).where(
            SubjectGroup.school_id == school_id,
            SubjectGroup.group_name == name,
            SubjectGroup.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, SubjectGroup) else None

    async def exists(self, school_id: uuid.UUID, code: str) -> bool:
        stmt = select(func.count(SubjectGroup.id)).where(
            SubjectGroup.school_id == school_id,
            SubjectGroup.group_code == code,
            SubjectGroup.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        category: str | None = None,
        status: SubjectGroupStatus | None = None,
        is_core: bool | None = None,
        is_elective: bool | None = None,
        query: str | None = None,
        sort_by: str | None = "display_order",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SubjectGroup], int]:
        stmt = select(SubjectGroup).where(
            SubjectGroup.school_id == school_id,
            SubjectGroup.is_deleted == False,
        )

        if category:
            stmt = stmt.where(SubjectGroup.category.ilike(f"%{category}%"))
        if status:
            stmt = stmt.where(SubjectGroup.status == status)
        if is_core is not None:
            stmt = stmt.where(SubjectGroup.is_core == is_core)
        if is_elective is not None:
            stmt = stmt.where(SubjectGroup.is_elective == is_elective)
        if query:
            stmt = stmt.where(
                or_(
                    SubjectGroup.group_name.ilike(f"%{query}%"),
                    SubjectGroup.group_code.ilike(f"%{query}%"),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        sort_columns = {
            "name": SubjectGroup.group_name,
            "created_at": SubjectGroup.created_at,
            "display_order": SubjectGroup.display_order,
        }
        col = sort_columns.get(sort_by or "display_order", SubjectGroup.display_order)
        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    # ==========================
    # Subject Mapping Operations
    # ==========================

    async def add_subject(
        self,
        school_id: uuid.UUID,
        subject_group_id: uuid.UUID,
        subject_id: uuid.UUID,
        display_order: int = 0,
        is_mandatory: bool = True,
    ) -> SubjectGroupMapping:
        mapping = SubjectGroupMapping(
            school_id=school_id,
            subject_group_id=subject_group_id,
            subject_id=subject_id,
            display_order=display_order,
            is_mandatory=is_mandatory,
        )
        self.session.add(mapping)
        return mapping

    async def remove_subject(
        self, subject_group_id: uuid.UUID, subject_id: uuid.UUID
    ) -> bool:
        stmt = select(SubjectGroupMapping).where(
            SubjectGroupMapping.subject_group_id == subject_group_id,
            SubjectGroupMapping.subject_id == subject_id,
            SubjectGroupMapping.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        mapping = result.scalar_one_or_none()
        if mapping:
            mapping.is_deleted = True
            mapping.deleted_at = func.now()
            self.session.add(mapping)
            return True
        return False

    async def get_mapping(
        self, subject_group_id: uuid.UUID, subject_id: uuid.UUID
    ) -> SubjectGroupMapping | None:
        stmt = select(SubjectGroupMapping).where(
            SubjectGroupMapping.subject_group_id == subject_group_id,
            SubjectGroupMapping.subject_id == subject_id,
            SubjectGroupMapping.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, SubjectGroupMapping) else None

    async def list_subjects(
        self, subject_group_id: uuid.UUID
    ) -> list[SubjectGroupMapping]:
        stmt = (
            select(SubjectGroupMapping)
            .options(selectinload(SubjectGroupMapping.subject))
            .where(
                SubjectGroupMapping.subject_group_id == subject_group_id,
                SubjectGroupMapping.is_deleted == False,
            )
            .order_by(SubjectGroupMapping.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
