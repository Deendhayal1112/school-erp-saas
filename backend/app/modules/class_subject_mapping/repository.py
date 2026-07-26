import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.modules.class_subject_mapping.enums import ClassSubjectStatus
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.subject_management.models import Subject


class ClassSubjectRepository:
    """
    Repository class encapsulating database query operations for Class Subject Mappings.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, mapping: ClassSubject) -> ClassSubject:
        self.session.add(mapping)
        return mapping

    async def update(self, mapping: ClassSubject) -> ClassSubject:
        self.session.add(mapping)
        return mapping

    async def delete(self, mapping_id: uuid.UUID) -> bool:
        mapping = await self.get_by_id(mapping_id, include_deleted=True)
        if mapping and not mapping.is_deleted:
            mapping.is_deleted = True
            mapping.deleted_at = func.now()
            self.session.add(mapping)
            return True
        return False

    async def restore(self, mapping_id: uuid.UUID) -> bool:
        mapping = await self.get_by_id(mapping_id, include_deleted=True)
        if mapping and mapping.is_deleted:
            mapping.is_deleted = False
            mapping.deleted_at = None
            self.session.add(mapping)
            return True
        return False

    async def get_by_id(
        self, mapping_id: uuid.UUID, include_deleted: bool = False
    ) -> ClassSubject | None:
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(ClassSubject.id == mapping_id)
        )
        if not include_deleted:
            stmt = stmt.where(ClassSubject.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, ClassSubject) else None

    async def get_by_class(
        self, school_id: uuid.UUID, class_id: uuid.UUID
    ) -> list[ClassSubject]:
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(
                ClassSubject.school_id == school_id,
                ClassSubject.class_id == class_id,
                ClassSubject.is_deleted == False,
            )
            .order_by(ClassSubject.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_section(
        self, school_id: uuid.UUID, section_id: uuid.UUID
    ) -> list[ClassSubject]:
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(
                ClassSubject.school_id == school_id,
                ClassSubject.section_id == section_id,
                ClassSubject.is_deleted == False,
            )
            .order_by(ClassSubject.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_subject(
        self, school_id: uuid.UUID, subject_id: uuid.UUID
    ) -> list[ClassSubject]:
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(
                ClassSubject.school_id == school_id,
                ClassSubject.subject_id == subject_id,
                ClassSubject.is_deleted == False,
            )
            .order_by(ClassSubject.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_term(
        self, school_id: uuid.UUID, term_id: uuid.UUID
    ) -> list[ClassSubject]:
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(
                ClassSubject.school_id == school_id,
                ClassSubject.term_id == term_id,
                ClassSubject.is_deleted == False,
            )
            .order_by(ClassSubject.display_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID | None,
        subject_id: uuid.UUID,
    ) -> bool:
        stmt = select(func.count(ClassSubject.id)).where(
            ClassSubject.school_id == school_id,
            ClassSubject.academic_year_id == academic_year_id,
            ClassSubject.term_id == term_id,
            ClassSubject.class_id == class_id,
            ClassSubject.section_id == section_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def check_display_order_exists(
        self,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        display_order: int,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = select(func.count(ClassSubject.id)).where(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.term_id == term_id,
            ClassSubject.display_order == display_order,
            ClassSubject.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(ClassSubject.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        subject_group_id: uuid.UUID | None = None,
        is_compulsory: bool | None = None,
        is_elective: bool | None = None,
        status: ClassSubjectStatus | None = None,
        sort_by: str | None = "display_order",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ClassSubject], int]:
        stmt = (
            select(ClassSubject)
            .options(selectinload(ClassSubject.subject))
            .where(
                ClassSubject.school_id == school_id,
                ClassSubject.is_deleted == False,
            )
        )

        if academic_year_id:
            stmt = stmt.where(ClassSubject.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(ClassSubject.term_id == term_id)
        if class_id:
            stmt = stmt.where(ClassSubject.class_id == class_id)
        if section_id:
            stmt = stmt.where(ClassSubject.section_id == section_id)
        if subject_id:
            stmt = stmt.where(ClassSubject.subject_id == subject_id)
        if subject_group_id:
            stmt = stmt.where(ClassSubject.subject_group_id == subject_group_id)
        if is_compulsory is not None:
            stmt = stmt.where(ClassSubject.is_compulsory == is_compulsory)
        if is_elective is not None:
            stmt = stmt.where(ClassSubject.is_elective == is_elective)
        if status:
            stmt = stmt.where(ClassSubject.status == status)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        col: Any = ClassSubject.display_order
        if sort_by == "subject_name":
            stmt = stmt.join(ClassSubject.subject)
            col = Subject.display_name
        elif sort_by == "created_at":
            col = ClassSubject.created_at
        else:
            col = ClassSubject.display_order

        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
