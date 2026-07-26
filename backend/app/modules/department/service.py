import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.department.enums import DepartmentStatus
from app.modules.department.exceptions import (
    DepartmentNotFoundException,
    InvalidDepartmentException,
)
from app.modules.department.models import Department
from app.modules.department.repository import DepartmentRepository
from app.modules.department.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
)
from app.modules.department.validators import validate_department_data


class DepartmentService:
    """
    Service class orchestrating business actions, cache invalidation,
    and audit tracking for Department Management.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = DepartmentRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, id: uuid.UUID | None = None
    ) -> None:
        """Helper clearing cached list and detail lookups."""
        await self.cache.delete_pattern(f"department:list:{school_id}*")
        if id:
            await self.cache.delete(f"department:detail:{id}")

    async def create_department(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: DepartmentCreate,
    ) -> Department:
        # 1. School must exist and be active
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidDepartmentException("School does not exist or is inactive.")

        # 2. Validate structural constraints
        validate_department_data(
            budget=data.budget,
            email=data.email,
            phone=data.phone,
        )

        # 3. Department Code unique within School
        if await self.repo.exists_code(school_id, data.department_code):
            raise InvalidDepartmentException(
                f"Department code '{data.department_code}' already exists for this school."
            )

        # 4. Department Name unique within School
        if await self.repo.exists_name(school_id, data.department_name):
            raise InvalidDepartmentException(
                f"Department name '{data.department_name}' already exists for this school."
            )

        dept = Department(
            school_id=school_id,
            department_code=data.department_code,
            department_name=data.department_name,
            display_name=data.display_name,
            description=data.description,
            head_employee_id=data.head_employee_id,
            phone=data.phone,
            email=data.email,
            location=data.location,
            building=data.building,
            floor=data.floor,
            budget=data.budget,
            cost_center=data.cost_center,
            display_order=data.display_order,
            status=DepartmentStatus.ACTIVE,
            is_academic=data.is_academic,
            is_active=True,
            is_locked=False,
            created_by=user_id,
        )

        await self.repo.create(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="create",
            entity_name="Department",
            entity_id=dept.id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def update_department(
        self,
        dept_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: DepartmentUpdate,
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        # Cannot modify locked department
        if dept.is_locked:
            raise InvalidDepartmentException("Cannot modify locked Department.")

        # Validate budget if updated
        budget_val = data.budget if data.budget is not None else dept.budget
        email_val = data.email if data.email is not None else dept.email
        phone_val = data.phone if data.phone is not None else dept.phone

        validate_department_data(
            budget=budget_val,
            email=email_val,
            phone=phone_val,
        )

        # Uniqueness checks
        if (
            data.department_name is not None
            and data.department_name.lower() != dept.department_name.lower()
        ):
            if await self.repo.exists_name(
                school_id, data.department_name, exclude_id=dept_id
            ):
                raise InvalidDepartmentException(
                    f"Department name '{data.department_name}' already exists."
                )

        # Update values
        if data.department_name is not None:
            dept.department_name = data.department_name
        if data.display_name is not None:
            dept.display_name = data.display_name
        if data.description is not None:
            dept.description = data.description
        if data.head_employee_id is not None:
            dept.head_employee_id = data.head_employee_id
        if data.phone is not None:
            dept.phone = data.phone
        if data.email is not None:
            dept.email = data.email
        if data.location is not None:
            dept.location = data.location
        if data.building is not None:
            dept.building = data.building
        if data.floor is not None:
            dept.floor = data.floor
        if data.budget is not None:
            dept.budget = data.budget
        if data.cost_center is not None:
            dept.cost_center = data.cost_center
        if data.display_order is not None:
            dept.display_order = data.display_order
        if data.is_academic is not None:
            dept.is_academic = data.is_academic

        dept.updated_by = user_id
        await self.repo.update(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="update",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def delete_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        # Cannot delete ACTIVE department
        if dept.status == DepartmentStatus.ACTIVE:
            raise InvalidDepartmentException(
                "Cannot delete ACTIVE Department. Please deactivate or archive it first."
            )

        await self.repo.delete(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="delete",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def restore_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id, include_deleted=True)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        if not dept.is_deleted:
            raise InvalidDepartmentException("Department is not deleted.")

        await self.repo.restore(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="restore",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def activate_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        # Cannot activate archived department
        if dept.status == DepartmentStatus.ARCHIVED:
            raise InvalidDepartmentException("Cannot activate archived Department.")

        dept.status = DepartmentStatus.ACTIVE
        dept.is_active = True
        dept.updated_by = user_id
        await self.repo.update(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="activate",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def deactivate_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        dept.status = DepartmentStatus.INACTIVE
        dept.is_active = False
        dept.updated_by = user_id
        await self.repo.update(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="deactivate",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def lock_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        dept.is_locked = True
        dept.updated_by = user_id
        await self.repo.update(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="lock",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def unlock_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        dept.is_locked = False
        dept.updated_by = user_id
        await self.repo.update(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="unlock",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def archive_department(
        self, dept_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Department:
        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        dept.status = DepartmentStatus.ARCHIVED
        dept.is_active = False
        dept.updated_by = user_id
        await self.repo.update(dept)
        await self.db.flush()

        await self._invalidate_cache(school_id, dept_id)

        # Audit
        await self.audit.log_action(
            module="department",
            action="archive",
            entity_name="Department",
            entity_id=dept_id,
            user_id=user_id,
            school_id=school_id,
        )

        return dept

    async def get_by_id_cached(
        self, dept_id: uuid.UUID, school_id: uuid.UUID
    ) -> Department:
        cache_key = f"department:detail:{dept_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Reconstruct Department instance shell
            return Department(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                department_code=cached["department_code"],
                department_name=cached["department_name"],
                display_name=cached["display_name"],
                description=cached["description"],
                head_employee_id=uuid.UUID(cached["head_employee_id"])
                if cached["head_employee_id"]
                else None,
                phone=cached["phone"],
                email=cached["email"],
                location=cached["location"],
                building=cached["building"],
                floor=cached["floor"],
                budget=float(cached["budget"]),
                cost_center=cached["cost_center"],
                display_order=cached["display_order"],
                status=DepartmentStatus(cached["status"]),
                is_academic=cached["is_academic"],
                is_active=cached["is_active"],
                is_locked=cached["is_locked"],
            )

        dept = await self.repo.get_by_id(dept_id)
        if not dept or dept.school_id != school_id:
            raise DepartmentNotFoundException()

        state = {
            "id": str(dept.id),
            "school_id": str(dept.school_id),
            "department_code": dept.department_code,
            "department_name": dept.department_name,
            "display_name": dept.display_name,
            "description": dept.description,
            "head_employee_id": str(dept.head_employee_id)
            if dept.head_employee_id
            else None,
            "phone": dept.phone,
            "email": dept.email,
            "location": dept.location,
            "building": dept.building,
            "floor": dept.floor,
            "budget": float(dept.budget),
            "cost_center": dept.cost_center,
            "display_order": dept.display_order,
            "status": dept.status.value,
            "is_academic": dept.is_academic,
            "is_active": dept.is_active,
            "is_locked": dept.is_locked,
        }
        await self.cache.set(cache_key, state, 3600)
        return dept
