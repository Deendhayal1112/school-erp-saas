import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.exceptions import (
    AcademicYearNotFoundException,
    InvalidAcademicYearDataException,
    OverlappingAcademicYearException,
)
from app.modules.academic_year.models import AcademicYear
from app.modules.academic_year.repository import AcademicYearRepository
from app.modules.academic_year.schemas import AcademicYearCreate, AcademicYearUpdate
from app.modules.academic_year.validators import validate_dates


class AcademicYearService:
    """
    Service class orchestrating business actions and validations for Academic Years.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AcademicYearRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(self, school_id: uuid.UUID) -> None:
        """Helper to clear cached active and default years for the school."""
        await self.cache.delete(f"ay:active:{school_id}")
        await self.cache.delete(f"ay:default:{school_id}")
        await self.cache.delete_pattern(f"ay:list:{school_id}*")
        await self.cache.delete_pattern(f"academic_dashboard:*:{school_id}*")

    async def create_academic_year(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AcademicYearCreate,
    ) -> AcademicYear:
        # 1. Verify school presence
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidAcademicYearDataException(
                "School does not exist or is inactive."
            )

        # 2. Validate dates
        validate_dates(data.start_date, data.end_date)

        # 3. Check uniqueness of code and name
        conflict_code = await self.repo.get_by_code(school_id, data.code)
        if conflict_code:
            raise InvalidAcademicYearDataException(
                f"Academic Year with code '{data.code}' already exists."
            )

        conflict_name = await self.repo.get_by_name(school_id, data.name)
        if conflict_name:
            raise InvalidAcademicYearDataException(
                f"Academic Year with name '{data.name}' already exists."
            )

        # 4. Check overlapping date ranges
        overlap = await self.repo.check_overlapping(
            school_id, data.start_date, data.end_date
        )
        if overlap:
            raise OverlappingAcademicYearException()

        ay = AcademicYear(
            school_id=school_id,
            name=data.name,
            code=data.code,
            start_date=data.start_date,
            end_date=data.end_date,
            description=data.description,
            is_active=False,
            is_default=False,
            is_locked=False,
            status=AcademicYearStatus.PLANNED,
            created_by=user_id,
        )

        await self.repo.create(ay)
        await self.db.flush()

        # Invalidate Cache
        await self._invalidate_cache(school_id)

        # Audit Log
        await self.audit.log_action(
            module="academic_year",
            action="create",
            entity_name="AcademicYear",
            entity_id=ay.id,
            metadata_json={"code": data.code, "name": data.name},
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def update_academic_year(
        self,
        ay_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AcademicYearUpdate,
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        # Cannot modify locked academic year
        if ay.is_locked:
            raise InvalidAcademicYearDataException(
                "Cannot modify locked Academic Year."
            )

        # Validate name uniqueness if changed
        if data.name and data.name != ay.name:
            conflict_name = await self.repo.get_by_name(school_id, data.name)
            if conflict_name:
                raise InvalidAcademicYearDataException(
                    f"Academic Year with name '{data.name}' already exists."
                )
            ay.name = data.name

        # Validate code uniqueness if changed
        if data.code and data.code != ay.code:
            conflict_code = await self.repo.get_by_code(school_id, data.code)
            if conflict_code:
                raise InvalidAcademicYearDataException(
                    f"Academic Year with code '{data.code}' already exists."
                )
            ay.code = data.code

        # Validate date adjustments
        start = data.start_date or ay.start_date
        end = data.end_date or ay.end_date
        validate_dates(start, end)

        if data.start_date or data.end_date:
            overlap = await self.repo.check_overlapping(
                school_id, start, end, exclude_id=ay_id
            )
            if overlap:
                raise OverlappingAcademicYearException()
            ay.start_date = start
            ay.end_date = end

        if data.description is not None:
            ay.description = data.description

        ay.updated_by = user_id
        await self.repo.update(ay)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        await self.audit.log_action(
            module="academic_year",
            action="update",
            entity_name="AcademicYear",
            entity_id=ay.id,
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def delete_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        # Cannot delete ACTIVE academic year
        if ay.status == AcademicYearStatus.ACTIVE:
            raise InvalidAcademicYearDataException(
                "Cannot delete active Academic Year."
            )

        res = await self.repo.delete(ay_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id)
            await self.audit.log_action(
                module="academic_year",
                action="delete",
                entity_name="AcademicYear",
                entity_id=ay_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        ay = await self.repo.get_by_id(ay_id, include_deleted=True)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        res = await self.repo.restore(ay_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id)
            await self.audit.log_action(
                module="academic_year",
                action="restore",
                entity_name="AcademicYear",
                entity_id=ay_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        # Cannot activate archived Academic Year
        if ay.status == AcademicYearStatus.ARCHIVED:
            raise InvalidAcademicYearDataException(
                "Cannot activate archived Academic Year."
            )

        # Deactivate any other active years
        other_active = await self.repo.list_other_active_years(school_id, ay_id)
        for oa in other_active:
            oa.status = AcademicYearStatus.COMPLETED
            oa.is_active = False
            await self.repo.update(oa)

        ay.status = AcademicYearStatus.ACTIVE
        ay.is_active = True
        await self.repo.update(ay)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        await self.audit.log_action(
            module="academic_year",
            action="activate",
            entity_name="AcademicYear",
            entity_id=ay_id,
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def deactivate_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        if ay.status == AcademicYearStatus.ACTIVE:
            ay.status = AcademicYearStatus.COMPLETED
            ay.is_active = False
            await self.repo.update(ay)
            await self.db.flush()

            await self._invalidate_cache(school_id)
            await self.audit.log_action(
                module="academic_year",
                action="deactivate",
                entity_name="AcademicYear",
                entity_id=ay_id,
                user_id=user_id,
                school_id=school_id,
            )

        return ay

    async def set_default_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        # Clear other default flags
        other_defaults = await self.repo.list_other_default_years(school_id, ay_id)
        for od in other_defaults:
            od.is_default = False
            await self.repo.update(od)

        ay.is_default = True
        await self.repo.update(ay)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        await self.audit.log_action(
            module="academic_year",
            action="set_default",
            entity_name="AcademicYear",
            entity_id=ay_id,
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def lock_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        ay.is_locked = True
        await self.repo.update(ay)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        await self.audit.log_action(
            module="academic_year",
            action="lock",
            entity_name="AcademicYear",
            entity_id=ay_id,
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def unlock_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        ay.is_locked = False
        await self.repo.update(ay)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        await self.audit.log_action(
            module="academic_year",
            action="unlock",
            entity_name="AcademicYear",
            entity_id=ay_id,
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def archive_academic_year(
        self, ay_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicYear:
        ay = await self.repo.get_by_id(ay_id)
        if not ay or ay.school_id != school_id:
            raise AcademicYearNotFoundException()

        ay.status = AcademicYearStatus.ARCHIVED
        ay.is_active = False
        await self.repo.update(ay)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        await self.audit.log_action(
            module="academic_year",
            action="archive",
            entity_name="AcademicYear",
            entity_id=ay_id,
            user_id=user_id,
            school_id=school_id,
        )

        return ay

    async def get_active_cached(self, school_id: uuid.UUID) -> AcademicYear | None:
        cache_key = f"ay:active:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AcademicYear(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                name=cached["name"],
                code=cached["code"],
                start_date=date.fromisoformat(cached["start_date"]),
                end_date=date.fromisoformat(cached["end_date"]),
                description=cached["description"],
                is_active=cached["is_active"],
                is_default=cached["is_default"],
                is_locked=cached["is_locked"],
                status=AcademicYearStatus(cached["status"]),
                created_by=uuid.UUID(cached["created_by"])
                if cached.get("created_by")
                else None,
                updated_by=uuid.UUID(cached["updated_by"])
                if cached.get("updated_by")
                else None,
            )

        ay = await self.repo.get_active(school_id)
        if ay:
            state_dict = {
                "id": str(ay.id),
                "school_id": str(ay.school_id),
                "name": ay.name,
                "code": ay.code,
                "start_date": ay.start_date.isoformat(),
                "end_date": ay.end_date.isoformat(),
                "description": ay.description,
                "is_active": ay.is_active,
                "is_default": ay.is_default,
                "is_locked": ay.is_locked,
                "status": ay.status.value,
                "created_by": str(ay.created_by) if ay.created_by else None,
                "updated_by": str(ay.updated_by) if ay.updated_by else None,
            }
            await self.cache.set(cache_key, state_dict, 3600)
        return ay

    async def get_default_cached(self, school_id: uuid.UUID) -> AcademicYear | None:
        cache_key = f"ay:default:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AcademicYear(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                name=cached["name"],
                code=cached["code"],
                start_date=date.fromisoformat(cached["start_date"]),
                end_date=date.fromisoformat(cached["end_date"]),
                description=cached["description"],
                is_active=cached["is_active"],
                is_default=cached["is_default"],
                is_locked=cached["is_locked"],
                status=AcademicYearStatus(cached["status"]),
                created_by=uuid.UUID(cached["created_by"])
                if cached.get("created_by")
                else None,
                updated_by=uuid.UUID(cached["updated_by"])
                if cached.get("updated_by")
                else None,
            )

        ay = await self.repo.get_default(school_id)
        if ay:
            state_dict = {
                "id": str(ay.id),
                "school_id": str(ay.school_id),
                "name": ay.name,
                "code": ay.code,
                "start_date": ay.start_date.isoformat(),
                "end_date": ay.end_date.isoformat(),
                "description": ay.description,
                "is_active": ay.is_active,
                "is_default": ay.is_default,
                "is_locked": ay.is_locked,
                "status": ay.status.value,
                "created_by": str(ay.created_by) if ay.created_by else None,
                "updated_by": str(ay.updated_by) if ay.updated_by else None,
            }
            await self.cache.set(cache_key, state_dict, 3600)
        return ay
