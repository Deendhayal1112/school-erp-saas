import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.department.exceptions import DepartmentNotFoundException
from app.modules.department.models import Department
from app.modules.designation.enums import DesignationStatus
from app.modules.designation.exceptions import (
    DesignationNotFoundException,
    InvalidDesignationException,
)
from app.modules.designation.models import Designation
from app.modules.designation.repository import DesignationRepository
from app.modules.designation.schemas import (
    DesignationCreate,
    DesignationUpdate,
)
from app.modules.designation.validators import validate_salary_range


class DesignationService:
    """
    Service class orchestrating business actions, cache invalidation,
    and audit tracking for Designation Management.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = DesignationRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self,
        school_id: uuid.UUID,
        id: uuid.UUID | None = None,
        dept_id: uuid.UUID | None = None,
    ) -> None:
        """Helper clearing cached list, department lists, and detail lookups."""
        await self.cache.delete_pattern(f"designation:list:{school_id}*")
        if id:
            await self.cache.delete(f"designation:detail:{id}")
        if dept_id:
            await self.cache.delete(f"designation:dept:{dept_id}")

    async def create_designation(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: DesignationCreate,
    ) -> Designation:
        # 1. School must exist and be active
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidDesignationException("School does not exist or is inactive.")

        # 2. Department must exist and belong to same school
        dept = await self.db.get(Department, data.department_id)
        if not dept or dept.is_deleted:
            raise DepartmentNotFoundException()
        if dept.school_id != school_id:
            raise InvalidDesignationException(
                "Department does not belong to the active school."
            )

        # 3. Validate salary range
        validate_salary_range(
            min_salary=data.minimum_salary, max_salary=data.maximum_salary
        )

        # 4. Designation Code unique within School
        if await self.repo.exists_code(school_id, data.designation_code):
            raise InvalidDesignationException(
                f"Designation code '{data.designation_code}' already exists for this school."
            )

        # 5. Designation Name unique within Department
        if await self.repo.exists_name(data.department_id, data.designation_name):
            raise InvalidDesignationException(
                f"Designation name '{data.designation_name}' already exists in this department."
            )

        des = Designation(
            school_id=school_id,
            department_id=data.department_id,
            designation_code=data.designation_code,
            designation_name=data.designation_name,
            display_name=data.display_name,
            description=data.description,
            employment_category=data.employment_category,
            job_level=data.job_level,
            grade=data.grade,
            salary_band=data.salary_band,
            minimum_salary=data.minimum_salary,
            maximum_salary=data.maximum_salary,
            display_order=data.display_order,
            status=DesignationStatus.ACTIVE,
            is_teaching=data.is_teaching,
            is_management=data.is_management,
            is_active=True,
            is_locked=False,
            created_by=user_id,
        )

        await self.repo.create(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id=data.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="create",
            entity_name="Designation",
            entity_id=des.id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def update_designation(
        self,
        des_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: DesignationUpdate,
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        # Cannot modify locked designation
        if des.is_locked:
            raise InvalidDesignationException("Cannot modify locked Designation.")

        # Validate salary range if updated
        min_sal = (
            data.minimum_salary
            if data.minimum_salary is not None
            else des.minimum_salary
        )
        max_sal = (
            data.maximum_salary
            if data.maximum_salary is not None
            else des.maximum_salary
        )
        validate_salary_range(min_salary=min_sal, max_salary=max_sal)

        # Uniqueness checks
        if (
            data.designation_name is not None
            and data.designation_name.lower() != des.designation_name.lower()
        ):
            if await self.repo.exists_name(
                des.department_id, data.designation_name, exclude_id=des_id
            ):
                raise InvalidDesignationException(
                    f"Designation name '{data.designation_name}' already exists in this department."
                )

        # Update values
        if data.designation_name is not None:
            des.designation_name = data.designation_name
        if data.display_name is not None:
            des.display_name = data.display_name
        if data.description is not None:
            des.description = data.description
        if data.employment_category is not None:
            des.employment_category = data.employment_category
        if data.job_level is not None:
            des.job_level = data.job_level
        if data.grade is not None:
            des.grade = data.grade
        if data.salary_band is not None:
            des.salary_band = data.salary_band
        if data.minimum_salary is not None:
            des.minimum_salary = data.minimum_salary
        if data.maximum_salary is not None:
            des.maximum_salary = data.maximum_salary
        if data.display_order is not None:
            des.display_order = data.display_order
        if data.is_teaching is not None:
            des.is_teaching = data.is_teaching
        if data.is_management is not None:
            des.is_management = data.is_management

        des.updated_by = user_id
        await self.repo.update(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="update",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def delete_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        # Cannot delete ACTIVE designation
        if des.status == DesignationStatus.ACTIVE:
            raise InvalidDesignationException(
                "Cannot delete ACTIVE Designation. Please deactivate or archive it first."
            )

        await self.repo.delete(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="delete",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def restore_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id, include_deleted=True)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        if not des.is_deleted:
            raise InvalidDesignationException("Designation is not deleted.")

        await self.repo.restore(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="restore",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def activate_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        # Cannot activate archived designation
        if des.status == DesignationStatus.ARCHIVED:
            raise InvalidDesignationException("Cannot activate archived Designation.")

        des.status = DesignationStatus.ACTIVE
        des.is_active = True
        des.updated_by = user_id
        await self.repo.update(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="activate",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def deactivate_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        des.status = DesignationStatus.INACTIVE
        des.is_active = False
        des.updated_by = user_id
        await self.repo.update(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="deactivate",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def lock_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        des.is_locked = True
        des.updated_by = user_id
        await self.repo.update(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="lock",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def unlock_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        des.is_locked = False
        des.updated_by = user_id
        await self.repo.update(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="unlock",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def archive_designation(
        self, des_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Designation:
        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        des.status = DesignationStatus.ARCHIVED
        des.is_active = False
        des.updated_by = user_id
        await self.repo.update(des)
        await self.db.flush()

        await self._invalidate_cache(school_id, des_id, des.department_id)

        # Audit
        await self.audit.log_action(
            module="designation",
            action="archive",
            entity_name="Designation",
            entity_id=des_id,
            user_id=user_id,
            school_id=school_id,
        )

        return des

    async def get_by_id_cached(
        self, des_id: uuid.UUID, school_id: uuid.UUID
    ) -> Designation:
        cache_key = f"designation:detail:{des_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return Designation(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                department_id=uuid.UUID(cached["department_id"]),
                designation_code=cached["designation_code"],
                designation_name=cached["designation_name"],
                display_name=cached["display_name"],
                description=cached["description"],
                employment_category=cached["employment_category"],
                job_level=cached["job_level"],
                grade=cached["grade"],
                salary_band=cached["salary_band"],
                minimum_salary=float(cached["minimum_salary"]),
                maximum_salary=float(cached["maximum_salary"]),
                display_order=cached["display_order"],
                status=DesignationStatus(cached["status"]),
                is_teaching=cached["is_teaching"],
                is_management=cached["is_management"],
                is_active=cached["is_active"],
                is_locked=cached["is_locked"],
            )

        des = await self.repo.get_by_id(des_id)
        if not des or des.school_id != school_id:
            raise DesignationNotFoundException()

        state = {
            "id": str(des.id),
            "school_id": str(des.school_id),
            "department_id": str(des.department_id),
            "designation_code": des.designation_code,
            "designation_name": des.designation_name,
            "display_name": des.display_name,
            "description": des.description,
            "employment_category": des.employment_category,
            "job_level": des.job_level,
            "grade": des.grade,
            "salary_band": des.salary_band,
            "minimum_salary": float(des.minimum_salary),
            "maximum_salary": float(des.maximum_salary),
            "display_order": des.display_order,
            "status": des.status.value,
            "is_teaching": des.is_teaching,
            "is_management": des.is_management,
            "is_active": des.is_active,
            "is_locked": des.is_locked,
        }
        await self.cache.set(cache_key, state, 3600)
        return des

    async def get_by_department_cached(
        self, dept_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[Designation]:
        # Verify department belongs to the school
        dept = await self.db.get(Department, dept_id)
        if not dept or dept.is_deleted or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        cache_key = f"designation:dept:{dept_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [
                Designation(
                    id=uuid.UUID(i["id"]),
                    school_id=uuid.UUID(i["school_id"]),
                    department_id=uuid.UUID(i["department_id"]),
                    designation_code=i["designation_code"],
                    designation_name=i["designation_name"],
                    display_name=i["display_name"],
                    description=i["description"],
                    employment_category=i["employment_category"],
                    job_level=i["job_level"],
                    grade=i["grade"],
                    salary_band=i["salary_band"],
                    minimum_salary=float(i["minimum_salary"]),
                    maximum_salary=float(i["maximum_salary"]),
                    display_order=i["display_order"],
                    status=DesignationStatus(i["status"]),
                    is_teaching=i["is_teaching"],
                    is_management=i["is_management"],
                    is_active=i["is_active"],
                    is_locked=i["is_locked"],
                )
                for i in cached
            ]

        items = await self.repo.get_by_department(dept_id)
        state = [
            {
                "id": str(i.id),
                "school_id": str(i.school_id),
                "department_id": str(i.department_id),
                "designation_code": i.designation_code,
                "designation_name": i.designation_name,
                "display_name": i.display_name,
                "description": i.description,
                "employment_category": i.employment_category,
                "job_level": i.job_level,
                "grade": i.grade,
                "salary_band": i.salary_band,
                "minimum_salary": float(i.minimum_salary),
                "maximum_salary": float(i.maximum_salary),
                "display_order": i.display_order,
                "status": i.status.value,
                "is_teaching": i.is_teaching,
                "is_management": i.is_management,
                "is_active": i.is_active,
                "is_locked": i.is_locked,
            }
            for i in items
        ]
        await self.cache.set(cache_key, state, 3600)
        return items
