import uuid
from typing import Any

from sqlalchemy import func, or_, select

from app.modules.subject_management.enums import SubjectStatus, SubjectType
from app.modules.subject_management.models import Subject


class SubjectRepository:
    """
    Repository class encapsulating database query operations for Subjects.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, subject: Subject) -> Subject:
        self.session.add(subject)
        return subject

    async def update(self, subject: Subject) -> Subject:
        self.session.add(subject)
        return subject

    async def delete(self, subject_id: uuid.UUID) -> bool:
        sub = await self.get_by_id(subject_id, include_deleted=True)
        if sub and not sub.is_deleted:
            sub.is_deleted = True
            sub.deleted_at = func.now()
            self.session.add(sub)
            return True
        return False

    async def restore(self, subject_id: uuid.UUID) -> bool:
        sub = await self.get_by_id(subject_id, include_deleted=True)
        if sub and sub.is_deleted:
            sub.is_deleted = False
            sub.deleted_at = None
            self.session.add(sub)
            return True
        return False

    async def get_by_id(
        self, subject_id: uuid.UUID, include_deleted: bool = False
    ) -> Subject | None:
        stmt = select(Subject).where(Subject.id == subject_id)
        if not include_deleted:
            stmt = stmt.where(Subject.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Subject) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> Subject | None:
        stmt = select(Subject).where(
            Subject.school_id == school_id,
            Subject.subject_code == code,
            Subject.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Subject) else None

    async def get_by_name(self, school_id: uuid.UUID, name: str) -> Subject | None:
        stmt = select(Subject).where(
            Subject.school_id == school_id,
            Subject.subject_name == name,
            Subject.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Subject) else None

    async def exists(self, school_id: uuid.UUID, code: str) -> bool:
        stmt = select(func.count(Subject.id)).where(
            Subject.school_id == school_id,
            Subject.subject_code == code,
            Subject.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        subject_type: SubjectType | None = None,
        category: str | None = None,
        status: SubjectStatus | None = None,
        language: str | None = None,
        is_core: bool | None = None,
        is_elective: bool | None = None,
        query: str | None = None,
        sort_by: str | None = "display_order",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Subject], int]:
        stmt = select(Subject).where(
            Subject.school_id == school_id,
            Subject.is_deleted == False,
        )

        # Filters
        if subject_type:
            stmt = stmt.where(Subject.subject_type == subject_type)
        if category:
            stmt = stmt.where(Subject.category.ilike(f"%{category}%"))
        if status:
            stmt = stmt.where(Subject.status == status)
        if language:
            stmt = stmt.where(Subject.language.ilike(f"%{language}%"))
        if is_core is not None:
            stmt = stmt.where(Subject.is_core == is_core)
        if is_elective is not None:
            stmt = stmt.where(Subject.is_elective == is_elective)
        if query:
            stmt = stmt.where(
                or_(
                    Subject.subject_name.ilike(f"%{query}%"),
                    Subject.subject_code.ilike(f"%{query}%"),
                    Subject.display_name.ilike(f"%{query}%"),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        sort_columns = {
            "name": Subject.subject_name,
            "code": Subject.subject_code,
            "credits": Subject.credits,
            "display_order": Subject.display_order,
        }
        col = sort_columns.get(sort_by or "display_order", Subject.display_order)
        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
