import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.class_model import SchoolClass
from app.models.school import School
from app.modules.academic_year.models import AcademicYear
from app.modules.section_management.enums import SectionStatus
from app.modules.section_management.exceptions import (
    InvalidSectionDataException,
    SectionNotFoundException,
)
from app.modules.section_management.models import Section
from app.modules.section_management.repository import SectionRepository
from app.modules.section_management.schemas import SectionCreate, SectionUpdate
from app.modules.section_management.validators import validate_capacity


class SectionService:
    """
    Service class orchestrating business actions and validations for Sections.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SectionRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID, class_id: uuid.UUID
    ) -> None:
        """Helper to clear cached section items context."""
        await self.cache.delete(f"section:class:{class_id}")
        await self.cache.delete(f"section:ay:{academic_year_id}")
        await self.cache.delete_pattern(f"section:list:{school_id}*")
        await self.cache.delete_pattern(f"academic_dashboard:*:{school_id}*")

    async def create_section(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SectionCreate,
    ) -> Section:
        # 1. Verify School presence
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidSectionDataException("School does not exist or is inactive.")

        # 2. Verify Academic Year presence
        ay = await self.db.get(AcademicYear, data.academic_year_id)
        if not ay or ay.school_id != school_id or ay.is_deleted:
            raise InvalidSectionDataException(
                "Academic Year does not exist or is deleted."
            )

        # 3. Verify Class presence
        cls = await self.db.get(SchoolClass, data.class_id)
        if not cls or cls.school_id != school_id or cls.is_deleted:
            raise InvalidSectionDataException("Class does not exist or is deleted.")

        # 4. Verify Class alignment with Academic Year
        if cls.academic_year_id != data.academic_year_id:
            raise InvalidSectionDataException(
                "Class does not belong to the selected Academic Year."
            )

        # 5. Validate capacity > 0
        validate_capacity(data.capacity)

        # 6. Validate code unique per school
        conflict_code = await self.repo.get_by_code(school_id, data.code)
        if conflict_code:
            raise InvalidSectionDataException(
                f"Section with code '{data.code}' already exists."
            )

        # 7. Validate name unique per Class
        conflict_name = await self.repo.get_by_name(data.class_id, data.name)
        if conflict_name:
            raise InvalidSectionDataException(
                f"Section with name '{data.name}' already exists in this Class."
            )

        # 8. Validate display order unique per Class
        conflict_order = await self.repo.get_by_display_order(
            data.class_id, data.display_order
        )
        if conflict_order:
            raise InvalidSectionDataException(
                f"Section with display order {data.display_order} already exists in this Class."
            )

        sec = Section(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            name=data.name,
            code=data.code,
            display_name=data.display_name,
            description=data.description,
            capacity=data.capacity,
            display_order=data.display_order,
            room_number=data.room_number,
            floor=data.floor,
            building=data.building,
            is_default=False,
            is_locked=False,
            status=SectionStatus.PLANNED,
            created_by=user_id,
        )

        await self.repo.create(sec)
        await self.db.flush()

        # Invalidate Cache
        await self._invalidate_cache(school_id, data.academic_year_id, data.class_id)

        # Audit Log
        await self.audit.log_action(
            module="section",
            action="create",
            entity_name="Section",
            entity_id=sec.id,
            metadata_json={"code": data.code, "name": data.name},
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def update_section(
        self,
        section_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: SectionUpdate,
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        # Cannot modify locked section
        if sec.is_locked:
            raise InvalidSectionDataException("Cannot modify locked Section.")

        # Validate name uniqueness within class if updated
        if data.name and data.name != sec.name:
            conflict_name = await self.repo.get_by_name(sec.class_id, data.name)
            if conflict_name:
                raise InvalidSectionDataException(
                    f"Section with name '{data.name}' already exists in this Class."
                )
            sec.name = data.name

        # Validate code uniqueness if updated
        if data.code and data.code != sec.code:
            conflict_code = await self.repo.get_by_code(school_id, data.code)
            if conflict_code:
                raise InvalidSectionDataException(
                    f"Section with code '{data.code}' already exists."
                )
            sec.code = data.code

        # Validate capacity if updated
        if data.capacity is not None:
            validate_capacity(data.capacity)
            sec.capacity = data.capacity

        # Validate display order if updated
        if data.display_order is not None and data.display_order != sec.display_order:
            conflict_order = await self.repo.get_by_display_order(
                sec.class_id, data.display_order
            )
            if conflict_order:
                raise InvalidSectionDataException(
                    f"Section with display order {data.display_order} already exists in this Class."
                )
            sec.display_order = data.display_order

        if data.display_name is not None:
            sec.display_name = data.display_name
        if data.description is not None:
            sec.description = data.description
        if data.room_number is not None:
            sec.room_number = data.room_number
        if data.floor is not None:
            sec.floor = data.floor
        if data.building is not None:
            sec.building = data.building

        sec.updated_by = user_id
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="update",
            entity_name="Section",
            entity_id=sec.id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def delete_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        # Cannot delete active section
        if sec.status == SectionStatus.ACTIVE:
            raise InvalidSectionDataException("Cannot delete active Section.")

        res = await self.repo.delete(section_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)
            await self.audit.log_action(
                module="section",
                action="delete",
                entity_name="Section",
                entity_id=section_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        sec = await self.repo.get_by_id(section_id, include_deleted=True)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        res = await self.repo.restore(section_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)
            await self.audit.log_action(
                module="section",
                action="restore",
                entity_name="Section",
                entity_id=section_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        # Cannot activate archived section
        if sec.status == SectionStatus.ARCHIVED:
            raise InvalidSectionDataException("Cannot activate archived Section.")

        sec.status = SectionStatus.ACTIVE
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="activate",
            entity_name="Section",
            entity_id=section_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def deactivate_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        sec.status = SectionStatus.INACTIVE
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="deactivate",
            entity_name="Section",
            entity_id=section_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def set_default_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        # Clear other default flags for sections within the same Class
        other_defaults = await self.repo.list_other_default_sections(
            sec.class_id, section_id
        )
        for od in other_defaults:
            od.is_default = False
            await self.repo.update(od)

        sec.is_default = True
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="set_default",
            entity_name="Section",
            entity_id=section_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def lock_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        sec.is_locked = True
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="lock",
            entity_name="Section",
            entity_id=section_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def unlock_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        sec.is_locked = False
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="unlock",
            entity_name="Section",
            entity_id=section_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def archive_section(
        self, section_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Section:
        sec = await self.repo.get_by_id(section_id)
        if not sec or sec.school_id != school_id:
            raise SectionNotFoundException()

        sec.status = SectionStatus.ARCHIVED
        await self.repo.update(sec)
        await self.db.flush()

        await self._invalidate_cache(school_id, sec.academic_year_id, sec.class_id)

        await self.audit.log_action(
            module="section",
            action="archive",
            entity_name="Section",
            entity_id=section_id,
            user_id=user_id,
            school_id=school_id,
        )

        return sec

    async def get_by_class_cached(self, class_id: uuid.UUID) -> list[Section]:
        cache_key = f"section:class:{class_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [
                Section(
                    id=uuid.UUID(t["id"]),
                    school_id=uuid.UUID(t["school_id"]),
                    academic_year_id=uuid.UUID(t["academic_year_id"]),
                    class_id=uuid.UUID(t["class_id"]),
                    name=t["name"],
                    code=t["code"],
                    display_name=t["display_name"],
                    description=t["description"],
                    capacity=t["capacity"],
                    display_order=t["display_order"],
                    room_number=t["room_number"],
                    floor=t["floor"],
                    building=t["building"],
                    is_default=t["is_default"],
                    is_locked=t["is_locked"],
                    status=SectionStatus(t["status"]),
                    created_by=uuid.UUID(t["created_by"])
                    if t.get("created_by")
                    else None,
                    updated_by=uuid.UUID(t["updated_by"])
                    if t.get("updated_by")
                    else None,
                )
                for t in cached
            ]

        sections = await self.repo.get_by_class(class_id)
        state_list = [
            {
                "id": str(t.id),
                "school_id": str(t.school_id),
                "academic_year_id": str(t.academic_year_id),
                "class_id": str(t.class_id),
                "name": t.name,
                "code": t.code,
                "display_name": t.display_name,
                "description": t.description,
                "capacity": t.capacity,
                "display_order": t.display_order,
                "room_number": t.room_number,
                "floor": t.floor,
                "building": t.building,
                "is_default": t.is_default,
                "is_locked": t.is_locked,
                "status": t.status.value,
                "created_by": str(t.created_by) if t.created_by else None,
                "updated_by": str(t.updated_by) if t.updated_by else None,
            }
            for t in sections
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return sections

    async def get_by_academic_year_cached(
        self, academic_year_id: uuid.UUID
    ) -> list[Section]:
        cache_key = f"section:ay:{academic_year_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [
                Section(
                    id=uuid.UUID(t["id"]),
                    school_id=uuid.UUID(t["school_id"]),
                    academic_year_id=uuid.UUID(t["academic_year_id"]),
                    class_id=uuid.UUID(t["class_id"]),
                    name=t["name"],
                    code=t["code"],
                    display_name=t["display_name"],
                    description=t["description"],
                    capacity=t["capacity"],
                    display_order=t["display_order"],
                    room_number=t["room_number"],
                    floor=t["floor"],
                    building=t["building"],
                    is_default=t["is_default"],
                    is_locked=t["is_locked"],
                    status=SectionStatus(t["status"]),
                    created_by=uuid.UUID(t["created_by"])
                    if t.get("created_by")
                    else None,
                    updated_by=uuid.UUID(t["updated_by"])
                    if t.get("updated_by")
                    else None,
                )
                for t in cached
            ]

        sections = await self.repo.get_by_academic_year(academic_year_id)
        state_list = [
            {
                "id": str(t.id),
                "school_id": str(t.school_id),
                "academic_year_id": str(t.academic_year_id),
                "class_id": str(t.class_id),
                "name": t.name,
                "code": t.code,
                "display_name": t.display_name,
                "description": t.description,
                "capacity": t.capacity,
                "display_order": t.display_order,
                "room_number": t.room_number,
                "floor": t.floor,
                "building": t.building,
                "is_default": t.is_default,
                "is_locked": t.is_locked,
                "status": t.status.value,
                "created_by": str(t.created_by) if t.created_by else None,
                "updated_by": str(t.updated_by) if t.updated_by else None,
            }
            for t in sections
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return sections
