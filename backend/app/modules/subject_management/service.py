import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.subject_management.enums import SubjectStatus, SubjectType
from app.modules.subject_management.exceptions import (
    InvalidSubjectDataException,
    SubjectNotFoundException,
)
from app.modules.subject_management.models import Subject
from app.modules.subject_management.repository import SubjectRepository
from app.modules.subject_management.schemas import SubjectCreate, SubjectUpdate
from app.modules.subject_management.validators import validate_subject_data


class SubjectService:
    """
    Service class orchestrating business actions, rules, and cache invalidation for Subjects.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SubjectRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, subject_id: uuid.UUID | None = None
    ) -> None:
        """Clears cached list and detail caches associated with the school/subject context."""
        await self.cache.delete_pattern(f"subject:list:{school_id}*")
        if subject_id:
            await self.cache.delete(f"subject:detail:{subject_id}")

    async def create_subject(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SubjectCreate,
    ) -> Subject:
        # 1. School must exist
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidSubjectDataException("School does not exist or is inactive.")

        # 2. Validate input constraints
        validate_subject_data(
            subject_code=data.subject_code,
            subject_name=data.subject_name,
            display_name=data.display_name,
            credits=data.credits,
            weekly_periods=data.weekly_periods,
            theory_hours=data.theory_hours,
            practical_hours=data.practical_hours,
            passing_marks=data.passing_marks,
            maximum_marks=data.maximum_marks,
            display_order=data.display_order,
            subject_type=data.subject_type,
            language=data.language,
            is_core=data.is_core,
            is_elective=data.is_elective,
            has_practical=data.has_practical,
        )

        # 3. Subject Code unique within School
        conflict_code = await self.repo.get_by_code(school_id, data.subject_code)
        if conflict_code:
            raise InvalidSubjectDataException(
                f"Subject with code '{data.subject_code}' already exists."
            )

        # 4. Subject Name unique within School
        conflict_name = await self.repo.get_by_name(school_id, data.subject_name)
        if conflict_name:
            raise InvalidSubjectDataException(
                f"Subject with name '{data.subject_name}' already exists."
            )

        sub = Subject(
            school_id=school_id,
            subject_code=data.subject_code,
            subject_name=data.subject_name,
            short_name=data.short_name,
            display_name=data.display_name,
            description=data.description,
            subject_type=data.subject_type,
            category=data.category,
            credits=data.credits,
            weekly_periods=data.weekly_periods,
            theory_hours=data.theory_hours,
            practical_hours=data.practical_hours,
            passing_marks=data.passing_marks,
            maximum_marks=data.maximum_marks,
            language=data.language,
            is_core=data.is_core,
            is_elective=data.is_elective,
            has_practical=data.has_practical,
            display_order=data.display_order,
            status=SubjectStatus.ACTIVE,
            is_locked=False,
            created_by=user_id,
        )

        await self.repo.create(sub)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(school_id)

        # Audit Log
        await self.audit.log_action(
            module="subject",
            action="create",
            entity_name="Subject",
            entity_id=sub.id,
            metadata_json={"code": data.subject_code, "name": data.subject_name},
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def update_subject(
        self,
        subject_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SubjectUpdate,
    ) -> Subject:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        # Cannot modify locked subject
        if sub.is_locked:
            raise InvalidSubjectDataException("Cannot modify Locked Subject.")

        # Prepare parameters for validator, falling back to current values
        subject_code = (
            data.subject_code if data.subject_code is not None else sub.subject_code
        )
        subject_name = (
            data.subject_name if data.subject_name is not None else sub.subject_name
        )
        display_name = (
            data.display_name if data.display_name is not None else sub.display_name
        )
        credits_val = data.credits if data.credits is not None else sub.credits
        weekly_periods = (
            data.weekly_periods
            if data.weekly_periods is not None
            else sub.weekly_periods
        )
        theory_hours = (
            data.theory_hours if data.theory_hours is not None else sub.theory_hours
        )
        practical_hours = (
            data.practical_hours
            if data.practical_hours is not None
            else sub.practical_hours
        )
        passing_marks = (
            data.passing_marks if data.passing_marks is not None else sub.passing_marks
        )
        maximum_marks = (
            data.maximum_marks if data.maximum_marks is not None else sub.maximum_marks
        )
        display_order = (
            data.display_order if data.display_order is not None else sub.display_order
        )
        subject_type = (
            data.subject_type if data.subject_type is not None else sub.subject_type
        )
        language = data.language if data.language is not None else sub.language
        is_core = data.is_core if data.is_core is not None else sub.is_core
        is_elective = (
            data.is_elective if data.is_elective is not None else sub.is_elective
        )
        has_practical = (
            data.has_practical if data.has_practical is not None else sub.has_practical
        )

        validate_subject_data(
            subject_code=subject_code,
            subject_name=subject_name,
            display_name=display_name,
            credits=credits_val,
            weekly_periods=weekly_periods,
            theory_hours=theory_hours,
            practical_hours=practical_hours,
            passing_marks=passing_marks,
            maximum_marks=maximum_marks,
            display_order=display_order,
            subject_type=subject_type,
            language=language,
            is_core=is_core,
            is_elective=is_elective,
            has_practical=has_practical,
        )

        # Code unique checking
        if data.subject_code and data.subject_code != sub.subject_code:
            conflict_code = await self.repo.get_by_code(school_id, data.subject_code)
            if conflict_code:
                raise InvalidSubjectDataException(
                    f"Subject with code '{data.subject_code}' already exists."
                )
            sub.subject_code = data.subject_code

        # Name unique checking
        if data.subject_name and data.subject_name != sub.subject_name:
            conflict_name = await self.repo.get_by_name(school_id, data.subject_name)
            if conflict_name:
                raise InvalidSubjectDataException(
                    f"Subject with name '{data.subject_name}' already exists."
                )
            sub.subject_name = data.subject_name

        if data.short_name is not None:
            sub.short_name = data.short_name
        if data.display_name is not None:
            sub.display_name = data.display_name
        if data.description is not None:
            sub.description = data.description
        if data.subject_type is not None:
            sub.subject_type = data.subject_type
        if data.category is not None:
            sub.category = data.category
        if data.credits is not None:
            sub.credits = data.credits
        if data.weekly_periods is not None:
            sub.weekly_periods = data.weekly_periods
        if data.theory_hours is not None:
            sub.theory_hours = data.theory_hours
        if data.practical_hours is not None:
            sub.practical_hours = data.practical_hours
        if data.passing_marks is not None:
            sub.passing_marks = data.passing_marks
        if data.maximum_marks is not None:
            sub.maximum_marks = data.maximum_marks
        if data.language is not None:
            sub.language = data.language
        if data.is_core is not None:
            sub.is_core = data.is_core
        if data.is_elective is not None:
            sub.is_elective = data.is_elective
        if data.has_practical is not None:
            sub.has_practical = data.has_practical
        if data.display_order is not None:
            sub.display_order = data.display_order

        sub.updated_by = user_id
        await self.repo.update(sub)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(school_id, subject_id)

        # Audit Log
        await self.audit.log_action(
            module="subject",
            action="update",
            entity_name="Subject",
            entity_id=sub.id,
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def delete_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        # Cannot delete Active Subject
        if sub.status == SubjectStatus.ACTIVE:
            raise InvalidSubjectDataException("Cannot delete Active Subject.")

        res = await self.repo.delete(subject_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, subject_id)
            await self.audit.log_action(
                module="subject",
                action="delete",
                entity_name="Subject",
                entity_id=subject_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        sub = await self.repo.get_by_id(subject_id, include_deleted=True)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        res = await self.repo.restore(subject_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, subject_id)
            await self.audit.log_action(
                module="subject",
                action="restore",
                entity_name="Subject",
                entity_id=subject_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subject:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        # Cannot activate Archived Subject
        if sub.status == SubjectStatus.ARCHIVED:
            raise InvalidSubjectDataException("Cannot activate Archived Subject.")

        sub.status = SubjectStatus.ACTIVE
        sub.updated_by = user_id
        await self.repo.update(sub)
        await self.db.flush()

        await self._invalidate_cache(school_id, subject_id)

        await self.audit.log_action(
            module="subject",
            action="activate",
            entity_name="Subject",
            entity_id=subject_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def deactivate_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subject:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        sub.status = SubjectStatus.INACTIVE
        sub.updated_by = user_id
        await self.repo.update(sub)
        await self.db.flush()

        await self._invalidate_cache(school_id, subject_id)

        await self.audit.log_action(
            module="subject",
            action="deactivate",
            entity_name="Subject",
            entity_id=subject_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def lock_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subject:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        sub.is_locked = True
        sub.updated_by = user_id
        await self.repo.update(sub)
        await self.db.flush()

        await self._invalidate_cache(school_id, subject_id)

        await self.audit.log_action(
            module="subject",
            action="lock",
            entity_name="Subject",
            entity_id=subject_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def unlock_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subject:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        sub.is_locked = False
        sub.updated_by = user_id
        await self.repo.update(sub)
        await self.db.flush()

        await self._invalidate_cache(school_id, subject_id)

        await self.audit.log_action(
            module="subject",
            action="unlock",
            entity_name="Subject",
            entity_id=subject_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def archive_subject(
        self, subject_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subject:
        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        sub.status = SubjectStatus.ARCHIVED
        sub.updated_by = user_id
        await self.repo.update(sub)
        await self.db.flush()

        await self._invalidate_cache(school_id, subject_id)

        await self.audit.log_action(
            module="subject",
            action="archive",
            entity_name="Subject",
            entity_id=subject_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sub

    async def get_subject_cached(
        self, subject_id: uuid.UUID, school_id: uuid.UUID
    ) -> Subject:
        cache_key = f"subject:detail:{subject_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            if uuid.UUID(cached["school_id"]) != school_id:
                raise SubjectNotFoundException()
            return Subject(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                subject_code=cached["subject_code"],
                subject_name=cached["subject_name"],
                short_name=cached["short_name"],
                display_name=cached["display_name"],
                description=cached["description"],
                subject_type=SubjectType(cached["subject_type"]),
                category=cached["category"],
                credits=cached["credits"],
                weekly_periods=cached["weekly_periods"],
                theory_hours=cached["theory_hours"],
                practical_hours=cached["practical_hours"],
                passing_marks=cached["passing_marks"],
                maximum_marks=cached["maximum_marks"],
                language=cached["language"],
                is_core=cached["is_core"],
                is_elective=cached["is_elective"],
                has_practical=cached["has_practical"],
                display_order=cached["display_order"],
                status=SubjectStatus(cached["status"]),
                is_locked=cached["is_locked"],
                created_by=uuid.UUID(cached["created_by"])
                if cached.get("created_by")
                else None,
                updated_by=uuid.UUID(cached["updated_by"])
                if cached.get("updated_by")
                else None,
            )

        sub = await self.repo.get_by_id(subject_id)
        if not sub or sub.school_id != school_id:
            raise SubjectNotFoundException()

        state = {
            "id": str(sub.id),
            "school_id": str(sub.school_id),
            "subject_code": sub.subject_code,
            "subject_name": sub.subject_name,
            "short_name": sub.short_name,
            "display_name": sub.display_name,
            "description": sub.description,
            "subject_type": sub.subject_type.value,
            "category": sub.category,
            "credits": sub.credits,
            "weekly_periods": sub.weekly_periods,
            "theory_hours": sub.theory_hours,
            "practical_hours": sub.practical_hours,
            "passing_marks": sub.passing_marks,
            "maximum_marks": sub.maximum_marks,
            "language": sub.language,
            "is_core": sub.is_core,
            "is_elective": sub.is_elective,
            "has_practical": sub.has_practical,
            "display_order": sub.display_order,
            "status": sub.status.value,
            "is_locked": sub.is_locked,
            "created_by": str(sub.created_by) if sub.created_by else None,
            "updated_by": str(sub.updated_by) if sub.updated_by else None,
        }
        await self.cache.set(cache_key, state, 3600)
        return sub
