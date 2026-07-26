import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.class_subject_mapping.models import ClassSubject
from app.modules.curriculum.enums import CurriculumStatus
from app.modules.curriculum.exceptions import (
    CurriculumNotFoundException,
    CurriculumUnitNotFoundException,
    InvalidCurriculumException,
)
from app.modules.curriculum.models import Curriculum, CurriculumUnit
from app.modules.curriculum.repository import CurriculumRepository
from app.modules.curriculum.schemas import (
    CurriculumCreate,
    CurriculumUnitCreate,
    CurriculumUnitUpdate,
    CurriculumUpdate,
)
from app.modules.curriculum.validators import validate_curriculum_data
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


class CurriculumService:
    """
    Service class orchestrating business actions and cache invalidation for Curriculum & Units.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CurriculumRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, curriculum_id: uuid.UUID | None = None
    ) -> None:
        """Clears cached list, detail, and units lookup indices."""
        await self.cache.delete_pattern(f"curriculum:list:{school_id}*")
        if curriculum_id:
            await self.cache.delete(f"curriculum:detail:{curriculum_id}")
            await self.cache.delete(f"curriculum:units:{curriculum_id}")

    async def create_curriculum(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CurriculumCreate,
    ) -> Curriculum:
        # 1. School must exist
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidCurriculumException("School does not exist or is inactive.")

        # 2. Validate input constraints
        validate_curriculum_data(
            curriculum_code=data.curriculum_code,
            curriculum_name=data.curriculum_name,
            completion_percentage=data.completion_percentage,
            estimated_hours=data.estimated_hours,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )

        # 3. Academic Year must exist and be ACTIVE
        ay = await self.db.get(AcademicYear, data.academic_year_id)
        if not ay or ay.school_id != school_id or ay.is_deleted:
            raise InvalidCurriculumException("Academic Year does not exist.")
        if ay.status != AcademicYearStatus.ACTIVE:
            raise InvalidCurriculumException("Only ACTIVE Academic Year allowed.")

        # 4. Term must exist, belong to AY, and be ACTIVE
        term = await self.db.get(Term, data.term_id)
        if (
            not term
            or term.school_id != school_id
            or term.academic_year_id != data.academic_year_id
            or term.is_deleted
        ):
            raise InvalidCurriculumException(
                "Term does not exist or does not belong to Academic Year."
            )
        if term.status != TermStatus.ACTIVE:
            raise InvalidCurriculumException("Only ACTIVE Term allowed.")

        # 5. Class Subject Mapping must exist and belong to school
        mapping = await self.db.get(ClassSubject, data.class_subject_mapping_id)
        if not mapping or mapping.school_id != school_id or mapping.is_deleted:
            raise InvalidCurriculumException("Class Subject Mapping does not exist.")

        # 6. Curriculum Code unique within School
        conflict_code = await self.repo.get_by_code(school_id, data.curriculum_code)
        if conflict_code:
            raise InvalidCurriculumException(
                f"Curriculum with code '{data.curriculum_code}' already exists."
            )

        # 7. Curriculum Name unique within School
        conflict_name = await self.repo.get_by_name(school_id, data.curriculum_name)
        if conflict_name:
            raise InvalidCurriculumException(
                f"Curriculum with name '{data.curriculum_name}' already exists."
            )

        curr = Curriculum(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_subject_mapping_id=data.class_subject_mapping_id,
            curriculum_code=data.curriculum_code,
            curriculum_name=data.curriculum_name,
            description=data.description,
            learning_objectives=data.learning_objectives,
            teaching_methodology=data.teaching_methodology,
            assessment_strategy=data.assessment_strategy,
            reference_books=data.reference_books,
            completion_percentage=data.completion_percentage,
            estimated_hours=data.estimated_hours,
            display_order=data.display_order,
            status=CurriculumStatus.DRAFT,
            is_active=True,
            is_locked=False,
            version=data.version,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            created_by=user_id,
        )

        await self.repo.create(curr)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(school_id)

        # Audit Log
        await self.audit.log_action(
            module="curriculum",
            action="create",
            entity_name="Curriculum",
            entity_id=curr.id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    async def update_curriculum(
        self,
        curriculum_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CurriculumUpdate,
    ) -> Curriculum:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        # Locked Curriculum cannot be modified.
        if curr.is_locked:
            raise InvalidCurriculumException("Cannot modify locked Curriculum.")

        # Fallbacks for validation
        curriculum_code = (
            data.curriculum_code
            if data.curriculum_code is not None
            else curr.curriculum_code
        )
        curriculum_name = (
            data.curriculum_name
            if data.curriculum_name is not None
            else curr.curriculum_name
        )
        completion_percentage = (
            data.completion_percentage
            if data.completion_percentage is not None
            else curr.completion_percentage
        )
        estimated_hours = (
            data.estimated_hours
            if data.estimated_hours is not None
            else curr.estimated_hours
        )
        effective_from = (
            data.effective_from
            if data.effective_from is not None
            else curr.effective_from
        )
        effective_to = (
            data.effective_to if data.effective_to is not None else curr.effective_to
        )

        validate_curriculum_data(
            curriculum_code=curriculum_code,
            curriculum_name=curriculum_name,
            completion_percentage=completion_percentage,
            estimated_hours=estimated_hours,
            effective_from=effective_from,
            effective_to=effective_to,
        )

        # Code uniqueness check
        if data.curriculum_code and data.curriculum_code != curr.curriculum_code:
            conflict_code = await self.repo.get_by_code(school_id, data.curriculum_code)
            if conflict_code:
                raise InvalidCurriculumException(
                    f"Curriculum with code '{data.curriculum_code}' already exists."
                )
            curr.curriculum_code = data.curriculum_code

        # Name uniqueness check
        if data.curriculum_name and data.curriculum_name != curr.curriculum_name:
            conflict_name = await self.repo.get_by_name(school_id, data.curriculum_name)
            if conflict_name:
                raise InvalidCurriculumException(
                    f"Curriculum with name '{data.curriculum_name}' already exists."
                )
            curr.curriculum_name = data.curriculum_name

        if data.description is not None:
            curr.description = data.description
        if data.learning_objectives is not None:
            curr.learning_objectives = data.learning_objectives
        if data.teaching_methodology is not None:
            curr.teaching_methodology = data.teaching_methodology
        if data.assessment_strategy is not None:
            curr.assessment_strategy = data.assessment_strategy
        if data.reference_books is not None:
            curr.reference_books = data.reference_books
        if data.completion_percentage is not None:
            curr.completion_percentage = data.completion_percentage
        if data.estimated_hours is not None:
            curr.estimated_hours = data.estimated_hours
        if data.display_order is not None:
            curr.display_order = data.display_order
        if data.version is not None:
            curr.version = data.version
        if data.effective_from is not None:
            curr.effective_from = data.effective_from
        if data.effective_to is not None:
            curr.effective_to = data.effective_to

        curr.updated_by = user_id
        await self.repo.update(curr)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(school_id, curriculum_id)

        # Audit Log
        await self.audit.log_action(
            module="curriculum",
            action="update",
            entity_name="Curriculum",
            entity_id=curriculum_id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    async def delete_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        # Let's delete it
        res = await self.repo.delete(curriculum_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, curriculum_id)
            await self.audit.log_action(
                module="curriculum",
                action="delete",
                entity_name="Curriculum",
                entity_id=curriculum_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        curr = await self.repo.get_by_id(curriculum_id, include_deleted=True)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        res = await self.repo.restore(curriculum_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, curriculum_id)
            await self.audit.log_action(
                module="curriculum",
                action="restore",
                entity_name="Curriculum",
                entity_id=curriculum_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Curriculum:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        # Archived Curriculum cannot be activated.
        if curr.status == CurriculumStatus.ARCHIVED:
            raise InvalidCurriculumException("Cannot activate archived Curriculum.")

        curr.status = CurriculumStatus.ACTIVE
        curr.updated_by = user_id
        await self.repo.update(curr)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        await self.audit.log_action(
            module="curriculum",
            action="activate",
            entity_name="Curriculum",
            entity_id=curriculum_id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    async def deactivate_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Curriculum:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        curr.status = CurriculumStatus.DRAFT
        curr.updated_by = user_id
        await self.repo.update(curr)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        await self.audit.log_action(
            module="curriculum",
            action="deactivate",
            entity_name="Curriculum",
            entity_id=curriculum_id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    async def lock_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Curriculum:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        curr.is_locked = True
        curr.updated_by = user_id
        await self.repo.update(curr)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        await self.audit.log_action(
            module="curriculum",
            action="lock",
            entity_name="Curriculum",
            entity_id=curriculum_id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    async def unlock_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Curriculum:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        curr.is_locked = False
        curr.updated_by = user_id
        await self.repo.update(curr)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        await self.audit.log_action(
            module="curriculum",
            action="unlock",
            entity_name="Curriculum",
            entity_id=curriculum_id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    async def archive_curriculum(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Curriculum:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        curr.status = CurriculumStatus.ARCHIVED
        curr.updated_by = user_id
        await self.repo.update(curr)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        await self.audit.log_action(
            module="curriculum",
            action="archive",
            entity_name="Curriculum",
            entity_id=curriculum_id,
            user_id=user_id,
            school_id=school_id,
        )

        return curr

    # ==========================
    # Curriculum Unit Operations
    # ==========================

    async def add_curriculum_unit(
        self,
        curriculum_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CurriculumUnitCreate,
    ) -> CurriculumUnit:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        # Locked Curriculum cannot be modified.
        if curr.is_locked:
            raise InvalidCurriculumException(
                "Cannot modify units on a locked Curriculum."
            )

        # Unit Number unique per Curriculum
        conflict_num = await self.repo.get_unit_by_number(
            curriculum_id, data.unit_number
        )
        if conflict_num:
            raise InvalidCurriculumException(
                f"Unit with number {data.unit_number} already exists."
            )

        # Display Order unique per Curriculum
        conflict_order = await self.repo.get_unit_by_order(
            curriculum_id, data.display_order
        )
        if conflict_order:
            raise InvalidCurriculumException(
                f"Display Order {data.display_order} is already taken."
            )

        unit = CurriculumUnit(
            school_id=school_id,
            curriculum_id=curriculum_id,
            unit_number=data.unit_number,
            unit_name=data.unit_name,
            description=data.description,
            learning_outcomes=data.learning_outcomes,
            estimated_hours=data.estimated_hours,
            display_order=data.display_order,
            status=data.status,
        )

        await self.repo.add_unit(unit)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        # Audit
        await self.audit.log_action(
            module="curriculum",
            action="add_unit",
            entity_name="CurriculumUnit",
            entity_id=unit.id,
            user_id=user_id,
            school_id=school_id,
        )

        return unit

    async def update_curriculum_unit(
        self,
        curriculum_id: uuid.UUID,
        unit_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CurriculumUnitUpdate,
    ) -> CurriculumUnit:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        if curr.is_locked:
            raise InvalidCurriculumException(
                "Cannot modify units on a locked Curriculum."
            )

        unit = await self.repo.get_unit_by_id(unit_id)
        if not unit or unit.curriculum_id != curriculum_id:
            raise CurriculumUnitNotFoundException()

        # Unit Number uniqueness check
        if data.unit_number is not None and data.unit_number != unit.unit_number:
            conflict_num = await self.repo.get_unit_by_number(
                curriculum_id, data.unit_number
            )
            if conflict_num:
                raise InvalidCurriculumException(
                    f"Unit with number {data.unit_number} already exists."
                )
            unit.unit_number = data.unit_number

        # Display Order uniqueness check
        if data.display_order is not None and data.display_order != unit.display_order:
            conflict_order = await self.repo.get_unit_by_order(
                curriculum_id, data.display_order
            )
            if conflict_order:
                raise InvalidCurriculumException(
                    f"Display Order {data.display_order} is already taken."
                )
            unit.display_order = data.display_order

        if data.unit_name is not None:
            unit.unit_name = data.unit_name
        if data.description is not None:
            unit.description = data.description
        if data.learning_outcomes is not None:
            unit.learning_outcomes = data.learning_outcomes
        if data.estimated_hours is not None:
            unit.estimated_hours = data.estimated_hours
        if data.status is not None:
            unit.status = data.status

        await self.repo.update_unit(unit)
        await self.db.flush()

        await self._invalidate_cache(school_id, curriculum_id)

        # Audit
        await self.audit.log_action(
            module="curriculum",
            action="update_unit",
            entity_name="CurriculumUnit",
            entity_id=unit_id,
            user_id=user_id,
            school_id=school_id,
        )

        return unit

    async def delete_curriculum_unit(
        self,
        curriculum_id: uuid.UUID,
        unit_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        if curr.is_locked:
            raise InvalidCurriculumException(
                "Cannot modify units on a locked Curriculum."
            )

        unit = await self.repo.get_unit_by_id(unit_id)
        if not unit or unit.curriculum_id != curriculum_id:
            raise CurriculumUnitNotFoundException()

        res = await self.repo.delete_unit(unit_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, curriculum_id)
            await self.audit.log_action(
                module="curriculum",
                action="delete_unit",
                entity_name="CurriculumUnit",
                entity_id=unit_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def list_units_cached(
        self, curriculum_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[CurriculumUnit]:
        curr = await self.repo.get_by_id(curriculum_id)
        if not curr or curr.school_id != school_id:
            raise CurriculumNotFoundException()

        cache_key = f"curriculum:units:{curriculum_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [
                CurriculumUnit(
                    id=uuid.UUID(u["id"]),
                    school_id=uuid.UUID(u["school_id"]),
                    curriculum_id=uuid.UUID(u["curriculum_id"]),
                    unit_number=u["unit_number"],
                    unit_name=u["unit_name"],
                    description=u["description"],
                    learning_outcomes=u["learning_outcomes"],
                    estimated_hours=u["estimated_hours"],
                    display_order=u["display_order"],
                    status=u["status"],
                )
                for u in cached
            ]

        units = await self.repo.list_units(curriculum_id)
        state_list = [
            {
                "id": str(u.id),
                "school_id": str(u.school_id),
                "curriculum_id": str(u.curriculum_id),
                "unit_number": u.unit_number,
                "unit_name": u.unit_name,
                "description": u.description,
                "learning_outcomes": u.learning_outcomes,
                "estimated_hours": u.estimated_hours,
                "display_order": u.display_order,
                "status": u.status,
            }
            for u in units
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return units
