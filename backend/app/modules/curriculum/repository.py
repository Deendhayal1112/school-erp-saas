import uuid
from typing import Any

from sqlalchemy import func, select

from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.curriculum.enums import CurriculumStatus
from app.modules.curriculum.models import Curriculum, CurriculumUnit


class CurriculumRepository:
    """
    Repository class encapsulating database query operations for Curriculum and Units.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, curr: Curriculum) -> Curriculum:
        self.session.add(curr)
        return curr

    async def update(self, curr: Curriculum) -> Curriculum:
        self.session.add(curr)
        return curr

    async def delete(self, curriculum_id: uuid.UUID) -> bool:
        curr = await self.get_by_id(curriculum_id, include_deleted=True)
        if curr and not curr.is_deleted:
            curr.is_deleted = True
            curr.deleted_at = func.now()
            self.session.add(curr)
            return True
        return False

    async def restore(self, curriculum_id: uuid.UUID) -> bool:
        curr = await self.get_by_id(curriculum_id, include_deleted=True)
        if curr and curr.is_deleted:
            curr.is_deleted = False
            curr.deleted_at = None
            self.session.add(curr)
            return True
        return False

    async def get_by_id(
        self, curriculum_id: uuid.UUID, include_deleted: bool = False
    ) -> Curriculum | None:
        stmt = select(Curriculum).where(Curriculum.id == curriculum_id)
        if not include_deleted:
            stmt = stmt.where(Curriculum.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Curriculum) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> Curriculum | None:
        stmt = select(Curriculum).where(
            Curriculum.school_id == school_id,
            Curriculum.curriculum_code == code,
            Curriculum.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Curriculum) else None

    async def get_by_name(self, school_id: uuid.UUID, name: str) -> Curriculum | None:
        stmt = select(Curriculum).where(
            Curriculum.school_id == school_id,
            Curriculum.curriculum_name == name,
            Curriculum.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Curriculum) else None

    async def get_by_mapping(self, mapping_id: uuid.UUID) -> Curriculum | None:
        stmt = select(Curriculum).where(
            Curriculum.class_subject_mapping_id == mapping_id,
            Curriculum.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Curriculum) else None

    async def exists(self, school_id: uuid.UUID, code: str) -> bool:
        stmt = select(func.count(Curriculum.id)).where(
            Curriculum.school_id == school_id,
            Curriculum.curriculum_code == code,
            Curriculum.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_all(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        status: CurriculumStatus | None = None,
        completion_min: float | None = None,
        estimated_hours_max: int | None = None,
        sort_by: str | None = "display_order",
        sort_dir: str | None = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Curriculum], int]:
        stmt = select(Curriculum).where(
            Curriculum.school_id == school_id,
            Curriculum.is_deleted == False,
        )

        if academic_year_id:
            stmt = stmt.where(Curriculum.academic_year_id == academic_year_id)
        if term_id:
            stmt = stmt.where(Curriculum.term_id == term_id)
        if class_id or subject_id:
            # Join class subject mapping
            stmt = stmt.join(Curriculum.class_subject_mapping)
            if class_id:
                stmt = stmt.where(ClassSubject.class_id == class_id)
            if subject_id:
                stmt = stmt.where(ClassSubject.subject_id == subject_id)

        if status:
            stmt = stmt.where(Curriculum.status == status)
        if completion_min is not None:
            stmt = stmt.where(Curriculum.completion_percentage >= completion_min)
        if estimated_hours_max is not None:
            stmt = stmt.where(Curriculum.estimated_hours <= estimated_hours_max)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        # Let's map sorting columns
        col: Any = Curriculum.display_order
        if sort_by == "name":
            col = Curriculum.curriculum_name
        elif sort_by == "created_at":
            col = Curriculum.created_at

        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    # ==========================
    # Curriculum Unit Operations
    # ==========================

    async def add_unit(self, unit: CurriculumUnit) -> CurriculumUnit:
        self.session.add(unit)
        return unit

    async def update_unit(self, unit: CurriculumUnit) -> CurriculumUnit:
        self.session.add(unit)
        return unit

    async def delete_unit(self, unit_id: uuid.UUID) -> bool:
        unit = await self.get_unit_by_id(unit_id)
        if unit and not unit.is_deleted:
            unit.is_deleted = True
            unit.deleted_at = func.now()
            self.session.add(unit)
            return True
        return False

    async def get_unit_by_id(self, unit_id: uuid.UUID) -> CurriculumUnit | None:
        stmt = select(CurriculumUnit).where(
            CurriculumUnit.id == unit_id,
            CurriculumUnit.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, CurriculumUnit) else None

    async def get_unit_by_number(
        self, curriculum_id: uuid.UUID, number: int
    ) -> CurriculumUnit | None:
        stmt = select(CurriculumUnit).where(
            CurriculumUnit.curriculum_id == curriculum_id,
            CurriculumUnit.unit_number == number,
            CurriculumUnit.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, CurriculumUnit) else None

    async def get_unit_by_order(
        self, curriculum_id: uuid.UUID, order: int
    ) -> CurriculumUnit | None:
        stmt = select(CurriculumUnit).where(
            CurriculumUnit.curriculum_id == curriculum_id,
            CurriculumUnit.display_order == order,
            CurriculumUnit.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, CurriculumUnit) else None

    async def list_units(self, curriculum_id: uuid.UUID) -> list[CurriculumUnit]:
        stmt = select(CurriculumUnit).where(
            CurriculumUnit.curriculum_id == curriculum_id,
            CurriculumUnit.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
