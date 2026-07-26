import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.subject_group.enums import SubjectGroupStatus
from app.modules.subject_group.exceptions import (
    InvalidSubjectGroupDataException,
    SubjectGroupNotFoundException,
)
from app.modules.subject_group.models import SubjectGroup, SubjectGroupMapping
from app.modules.subject_group.repository import SubjectGroupRepository
from app.modules.subject_group.schemas import SubjectGroupCreate, SubjectGroupUpdate
from app.modules.subject_group.validators import validate_subject_group_data
from app.modules.subject_management.models import Subject


class SubjectGroupService:
    """
    Service class orchestrating business actions and cache invalidation for Subject Groups.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SubjectGroupRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, group_id: uuid.UUID | None = None
    ) -> None:
        """Clears cached list and detail caches associated with the school/group context."""
        await self.cache.delete_pattern(f"subject_group:list:{school_id}*")
        if group_id:
            await self.cache.delete(f"subject_group:detail:{group_id}")
            await self.cache.delete(f"subject_group:subjects:{group_id}")
        await self.cache.delete_pattern(f"academic_dashboard:*:{school_id}*")

    async def create_subject_group(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SubjectGroupCreate,
    ) -> SubjectGroup:
        # 1. School must exist
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidSubjectGroupDataException(
                "School does not exist or is inactive."
            )

        # 2. Validate input constraints
        validate_subject_group_data(
            group_name=data.group_name,
            group_code=data.group_code,
            display_name=data.display_name,
            display_order=data.display_order,
            minimum_subjects=data.minimum_subjects,
            maximum_subjects=data.maximum_subjects,
            is_core=data.is_core,
            is_elective=data.is_elective,
        )

        # 3. Group Code unique within School
        conflict_code = await self.repo.get_by_code(school_id, data.group_code)
        if conflict_code:
            raise InvalidSubjectGroupDataException(
                f"Subject Group with code '{data.group_code}' already exists."
            )

        # 4. Group Name unique within School
        conflict_name = await self.repo.get_by_name(school_id, data.group_name)
        if conflict_name:
            raise InvalidSubjectGroupDataException(
                f"Subject Group with name '{data.group_name}' already exists."
            )

        group = SubjectGroup(
            school_id=school_id,
            group_code=data.group_code,
            group_name=data.group_name,
            display_name=data.display_name,
            description=data.description,
            category=data.category,
            display_order=data.display_order,
            minimum_subjects=data.minimum_subjects,
            maximum_subjects=data.maximum_subjects,
            is_core=data.is_core,
            is_elective=data.is_elective,
            is_locked=False,
            status=SubjectGroupStatus.ACTIVE,
            created_by=user_id,
        )

        await self.repo.create(group)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(school_id)

        # Audit Log
        await self.audit.log_action(
            module="subject_group",
            action="create",
            entity_name="SubjectGroup",
            entity_id=group.id,
            metadata_json={"code": data.group_code, "name": data.group_name},
            user_id=user_id,
            school_id=school_id,
        )

        return group

    async def update_subject_group(
        self,
        group_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SubjectGroupUpdate,
    ) -> SubjectGroup:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        # Locked Subject Groups cannot be modified.
        if group.is_locked:
            raise InvalidSubjectGroupDataException(
                "Cannot modify locked Subject Group."
            )

        # Prepare parameters for validator, falling back to current values
        group_name = (
            data.group_name if data.group_name is not None else group.group_name
        )
        group_code = (
            data.group_code if data.group_code is not None else group.group_code
        )
        display_name = (
            data.display_name if data.display_name is not None else group.display_name
        )
        display_order = (
            data.display_order
            if data.display_order is not None
            else group.display_order
        )
        minimum_subjects = (
            data.minimum_subjects
            if data.minimum_subjects is not None
            else group.minimum_subjects
        )
        maximum_subjects = (
            data.maximum_subjects
            if data.maximum_subjects is not None
            else group.maximum_subjects
        )
        is_core = data.is_core if data.is_core is not None else group.is_core
        is_elective = (
            data.is_elective if data.is_elective is not None else group.is_elective
        )

        validate_subject_group_data(
            group_name=group_name,
            group_code=group_code,
            display_name=display_name,
            display_order=display_order,
            minimum_subjects=minimum_subjects,
            maximum_subjects=maximum_subjects,
            is_core=is_core,
            is_elective=is_elective,
        )

        # Code unique check
        if data.group_code and data.group_code != group.group_code:
            conflict_code = await self.repo.get_by_code(school_id, data.group_code)
            if conflict_code:
                raise InvalidSubjectGroupDataException(
                    f"Subject Group with code '{data.group_code}' already exists."
                )
            group.group_code = data.group_code

        # Name unique check
        if data.group_name and data.group_name != group.group_name:
            conflict_name = await self.repo.get_by_name(school_id, data.group_name)
            if conflict_name:
                raise InvalidSubjectGroupDataException(
                    f"Subject Group with name '{data.group_name}' already exists."
                )
            group.group_name = data.group_name

        if data.display_name is not None:
            group.display_name = data.display_name
        if data.description is not None:
            group.description = data.description
        if data.category is not None:
            group.category = data.category
        if data.display_order is not None:
            group.display_order = data.display_order
        if data.minimum_subjects is not None:
            group.minimum_subjects = data.minimum_subjects
        if data.maximum_subjects is not None:
            group.maximum_subjects = data.maximum_subjects
        if data.is_core is not None:
            group.is_core = data.is_core
        if data.is_elective is not None:
            group.is_elective = data.is_elective

        group.updated_by = user_id
        await self.repo.update(group)
        await self.db.flush()

        # Invalidate cache
        await self._invalidate_cache(school_id, group_id)

        # Audit Log
        await self.audit.log_action(
            module="subject_group",
            action="update",
            entity_name="SubjectGroup",
            entity_id=group.id,
            user_id=user_id,
            school_id=school_id,
        )

        return group

    async def delete_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        # Cannot delete ACTIVE Subject Group.
        if group.status == SubjectGroupStatus.ACTIVE:
            raise InvalidSubjectGroupDataException(
                "Cannot delete active Subject Group."
            )

        res = await self.repo.delete(group_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, group_id)
            await self.audit.log_action(
                module="subject_group",
                action="delete",
                entity_name="SubjectGroup",
                entity_id=group_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        group = await self.repo.get_by_id(group_id, include_deleted=True)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        res = await self.repo.restore(group_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, group_id)
            await self.audit.log_action(
                module="subject_group",
                action="restore",
                entity_name="SubjectGroup",
                entity_id=group_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubjectGroup:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        # Cannot activate ARCHIVED Subject Group.
        if group.status == SubjectGroupStatus.ARCHIVED:
            raise InvalidSubjectGroupDataException(
                "Cannot activate archived Subject Group."
            )

        group.status = SubjectGroupStatus.ACTIVE
        group.updated_by = user_id
        await self.repo.update(group)
        await self.db.flush()

        await self._invalidate_cache(school_id, group_id)

        await self.audit.log_action(
            module="subject_group",
            action="activate",
            entity_name="SubjectGroup",
            entity_id=group_id,
            user_id=user_id,
            school_id=school_id,
        )

        return group

    async def deactivate_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubjectGroup:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        group.status = SubjectGroupStatus.INACTIVE
        group.updated_by = user_id
        await self.repo.update(group)
        await self.db.flush()

        await self._invalidate_cache(school_id, group_id)

        await self.audit.log_action(
            module="subject_group",
            action="deactivate",
            entity_name="SubjectGroup",
            entity_id=group_id,
            user_id=user_id,
            school_id=school_id,
        )

        return group

    async def lock_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubjectGroup:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        group.is_locked = True
        group.updated_by = user_id
        await self.repo.update(group)
        await self.db.flush()

        await self._invalidate_cache(school_id, group_id)

        await self.audit.log_action(
            module="subject_group",
            action="lock",
            entity_name="SubjectGroup",
            entity_id=group_id,
            user_id=user_id,
            school_id=school_id,
        )

        return group

    async def unlock_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubjectGroup:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        group.is_locked = False
        group.updated_by = user_id
        await self.repo.update(group)
        await self.db.flush()

        await self._invalidate_cache(school_id, group_id)

        await self.audit.log_action(
            module="subject_group",
            action="unlock",
            entity_name="SubjectGroup",
            entity_id=group_id,
            user_id=user_id,
            school_id=school_id,
        )

        return group

    async def archive_subject_group(
        self, group_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubjectGroup:
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        group.status = SubjectGroupStatus.ARCHIVED
        group.updated_by = user_id
        await self.repo.update(group)
        await self.db.flush()

        await self._invalidate_cache(school_id, group_id)

        await self.audit.log_action(
            module="subject_group",
            action="archive",
            entity_name="SubjectGroup",
            entity_id=group_id,
            user_id=user_id,
            school_id=school_id,
        )

        return group

    # ==========================
    # Subject Mapping Logic
    # ==========================

    async def add_subject_mapping(
        self,
        group_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        display_order: int = 0,
        is_mandatory: bool = True,
    ) -> SubjectGroupMapping:
        # Check group exists
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        # Check group is not locked
        if group.is_locked:
            raise InvalidSubjectGroupDataException(
                "Cannot modify locked Subject Group."
            )

        # Check subject exists in school
        subject = await self.db.get(Subject, subject_id)
        if not subject or subject.school_id != school_id or subject.is_deleted:
            raise InvalidSubjectGroupDataException(
                "Subject does not exist or is deleted."
            )

        # Duplicate Subject Mapping not allowed.
        conflict = await self.repo.get_mapping(group_id, subject_id)
        if conflict:
            raise InvalidSubjectGroupDataException(
                "Subject is already mapped to this Subject Group."
            )

        mapping = await self.repo.add_subject(
            school_id=school_id,
            subject_group_id=group_id,
            subject_id=subject_id,
            display_order=display_order,
            is_mandatory=is_mandatory,
        )
        await self.db.flush()

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(SubjectGroupMapping)
            .options(selectinload(SubjectGroupMapping.subject))
            .where(SubjectGroupMapping.id == mapping.id)
            .execution_options(populate_existing=True)
        )
        mapping_loaded = (await self.db.execute(stmt)).scalar_one()

        # Invalidate caches
        await self._invalidate_cache(school_id, group_id)

        # Audit Log
        await self.audit.log_action(
            module="subject_group",
            action="add_subject",
            entity_name="SubjectGroupMapping",
            entity_id=mapping.id,
            metadata_json={"subject_id": str(subject_id), "group_id": str(group_id)},
            user_id=user_id,
            school_id=school_id,
        )

        return mapping_loaded

    async def remove_subject_mapping(
        self,
        group_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> bool:
        # Check group exists
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        # Check group is not locked
        if group.is_locked:
            raise InvalidSubjectGroupDataException(
                "Cannot modify locked Subject Group."
            )

        mapping = await self.repo.get_mapping(group_id, subject_id)
        if not mapping:
            raise InvalidSubjectGroupDataException("Subject mapping not found.")

        res = await self.repo.remove_subject(group_id, subject_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, group_id)
            await self.audit.log_action(
                module="subject_group",
                action="remove_subject",
                entity_name="SubjectGroupMapping",
                entity_id=mapping.id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def list_subjects_cached(
        self, group_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[SubjectGroupMapping]:
        # Validate group exists and belongs to tenant
        group = await self.repo.get_by_id(group_id)
        if not group or group.school_id != school_id:
            raise SubjectGroupNotFoundException()

        cache_key = f"subject_group:subjects:{group_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Map back to objects
            return [
                SubjectGroupMapping(
                    id=uuid.UUID(m["id"]),
                    school_id=uuid.UUID(m["school_id"]),
                    subject_group_id=uuid.UUID(m["subject_group_id"]),
                    subject_id=uuid.UUID(m["subject_id"]),
                    display_order=m["display_order"],
                    is_mandatory=m["is_mandatory"],
                    subject=Subject(
                        id=uuid.UUID(m["subject"]["id"]),
                        school_id=uuid.UUID(m["subject"]["school_id"]),
                        subject_code=m["subject"]["subject_code"],
                        subject_name=m["subject"]["subject_name"],
                        short_name=m["subject"]["short_name"],
                        display_name=m["subject"]["display_name"],
                        category=m["subject"]["category"],
                        credits=m["subject"]["credits"],
                        status=m["subject"]["status"],
                    )
                    if m.get("subject")
                    else None,
                )
                for m in cached
            ]

        mappings = await self.repo.list_subjects(group_id)
        state_list = [
            {
                "id": str(m.id),
                "school_id": str(m.school_id),
                "subject_group_id": str(m.subject_group_id),
                "subject_id": str(m.subject_id),
                "display_order": m.display_order,
                "is_mandatory": m.is_mandatory,
                "subject": {
                    "id": str(m.subject.id),
                    "school_id": str(m.subject.school_id),
                    "subject_code": m.subject.subject_code,
                    "subject_name": m.subject.subject_name,
                    "short_name": m.subject.short_name,
                    "display_name": m.subject.display_name,
                    "category": m.subject.category,
                    "credits": m.subject.credits,
                    "status": m.subject.status.value,
                }
                if m.subject
                else None,
            }
            for m in mappings
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return mappings
