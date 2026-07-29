import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.modules.academic_year.models import AcademicYear
from app.modules.department.models import Department
from app.modules.employee.models import Employee
from app.modules.teacher.constants import CACHE_TTL
from app.modules.teacher.exceptions import (
    InvalidTeacherException,
    TeacherNotFoundException,
)
from app.modules.teacher.models import Teacher
from app.modules.teacher.repository import TeacherRepository
from app.modules.teacher.schemas import TeacherCreate, TeacherResponse, TeacherUpdate
from app.modules.teacher.validators import (
    validate_max_teaching_hours,
    validate_official_email,
    validate_teacher_experience,
)


class TeacherService:
    """
    Service layer orchestrating business logic and workflows for Teacher profiles.
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = TeacherRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    def map_to_response(self, teacher: Teacher) -> TeacherResponse:
        return TeacherResponse.model_validate(teacher)

    async def _invalidate_cache(
        self, school_id: uuid.UUID, teacher_id: uuid.UUID, employee_id: uuid.UUID
    ) -> None:
        """Invalidates related caching keys."""
        await self.cache.delete(f"teacher:details:{teacher_id}")
        await self.cache.delete(f"teacher:employee:{employee_id}")
        await self.cache.delete_pattern("teacher:list:*")

    async def create_teacher_profile(
        self, data: TeacherCreate, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        # 1. Validation checks
        validate_teacher_experience(data.teaching_experience_years)
        validate_max_teaching_hours(data.max_teaching_hours_per_week)
        validate_official_email(data.official_email)

        # Check primary department
        dept = await self.db.get(Department, data.primary_department_id)
        if not dept or dept.is_deleted or dept.school_id != school_id:
            raise InvalidTeacherException(
                "Primary department not found or belongs to another school"
            )

        # Check joining academic year
        if data.joining_academic_year_id:
            ay = await self.db.get(AcademicYear, data.joining_academic_year_id)
            if not ay or ay.is_deleted or ay.school_id != school_id:
                raise InvalidTeacherException(
                    "Joining academic year not found or belongs to another school"
                )

        # Check employee
        emp = await self.db.get(Employee, data.employee_id)
        if not emp or emp.is_deleted or emp.school_id != school_id:
            raise InvalidTeacherException(
                "Employee not found or belongs to another school"
            )

        # Check One-to-One constraint
        existing_profile = await self.repo.get_by_employee(data.employee_id)
        if existing_profile:
            raise InvalidTeacherException("Employee already has a Teacher Profile")

        # Check teacher code unique within school
        if await self.repo.exists_code(school_id, data.teacher_code):
            raise InvalidTeacherException("Teacher code already exists in this school")

        # Check official email uniqueness
        if data.official_email and await self.repo.exists_official_email(
            school_id, data.official_email
        ):
            raise InvalidTeacherException("Official email already exists")

        # 2. Build profile
        teacher = Teacher(
            school_id=school_id,
            employee_id=data.employee_id,
            teacher_code=data.teacher_code,
            teacher_type=data.teacher_type,
            employment_mode=data.employment_mode,
            joining_academic_year_id=data.joining_academic_year_id,
            primary_department_id=data.primary_department_id,
            staff_room=data.staff_room,
            official_email=data.official_email,
            extension_number=data.extension_number,
            office_location=data.office_location,
            bio=data.bio,
            teaching_experience_years=data.teaching_experience_years,
            highest_qualification=data.highest_qualification,
            specialization=data.specialization,
            subject_preferences=data.subject_preferences,
            class_teacher_preference=data.class_teacher_preference,
            max_teaching_hours_per_week=data.max_teaching_hours_per_week,
            is_class_teacher=data.is_class_teacher,
            is_subject_teacher=data.is_subject_teacher,
            is_exam_evaluator=data.is_exam_evaluator,
            created_by=user_id,
            updated_by=user_id,
        )

        await self.repo.create(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, data.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="create",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def update_teacher_profile(
        self,
        teacher_id: uuid.UUID,
        data: TeacherUpdate,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        # Reject update on locked profile
        if teacher.is_locked:
            raise InvalidTeacherException("Cannot modify locked teacher")

        # Validate updates
        if data.teacher_code is not None and data.teacher_code != teacher.teacher_code:
            if await self.repo.exists_code(
                school_id, data.teacher_code, exclude_id=teacher_id
            ):
                raise InvalidTeacherException(
                    "Teacher code already exists in this school"
                )

        if (
            data.official_email is not None
            and data.official_email != teacher.official_email
        ):
            if data.official_email and await self.repo.exists_official_email(
                school_id, data.official_email, exclude_id=teacher_id
            ):
                raise InvalidTeacherException("Official email already exists")

        if (
            data.primary_department_id is not None
            and data.primary_department_id != teacher.primary_department_id
        ):
            dept = await self.db.get(Department, data.primary_department_id)
            if not dept or dept.is_deleted or dept.school_id != school_id:
                raise InvalidTeacherException(
                    "Primary department not found or belongs to another school"
                )

        if (
            data.joining_academic_year_id is not None
            and data.joining_academic_year_id != teacher.joining_academic_year_id
        ):
            ay = await self.db.get(AcademicYear, data.joining_academic_year_id)
            if not ay or ay.is_deleted or ay.school_id != school_id:
                raise InvalidTeacherException(
                    "Joining academic year not found or belongs to another school"
                )

        if data.teaching_experience_years is not None:
            validate_teacher_experience(data.teaching_experience_years)
        if data.max_teaching_hours_per_week is not None:
            validate_max_teaching_hours(data.max_teaching_hours_per_week)
        if data.official_email is not None:
            validate_official_email(data.official_email)

        # Apply properties
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(teacher, k, v)

        teacher.updated_by = user_id

        await self.repo.update(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="update",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def delete_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        if teacher.is_locked:
            raise InvalidTeacherException("Cannot modify locked teacher")

        await self.repo.delete(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="delete",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def restore_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id, include_deleted=True)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        if teacher.is_locked:
            raise InvalidTeacherException("Cannot modify locked teacher")

        await self.repo.restore(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="restore",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def activate_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        if teacher.is_locked:
            raise InvalidTeacherException("Cannot modify locked teacher")

        if teacher.is_archived:
            raise InvalidTeacherException("Cannot activate archived teacher")

        await self.repo.activate(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="activate",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def deactivate_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        if teacher.is_locked:
            raise InvalidTeacherException("Cannot modify locked teacher")

        await self.repo.deactivate(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="deactivate",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def lock_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        await self.repo.lock(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="lock",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def unlock_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        await self.repo.unlock(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="unlock",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def archive_teacher_profile(
        self, teacher_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        if teacher.is_locked:
            raise InvalidTeacherException("Cannot modify locked teacher")

        await self.repo.archive(teacher)
        await self.db.flush()

        await self._invalidate_cache(school_id, teacher.id, teacher.employee_id)

        # Audit
        await self.audit.log_action(
            module="teacher",
            action="archive",
            entity_name="Teacher",
            entity_id=teacher.id,
            user_id=user_id,
            school_id=school_id,
        )

        return teacher

    async def get_by_id_cached(
        self, teacher_id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherResponse:
        cache_key = f"teacher:details:{teacher_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return TeacherResponse.model_validate(cached)

        teacher = await self.repo.get_by_id(teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        resp = self.map_to_response(teacher)
        await self.cache.set(cache_key, resp.model_dump(mode="json"), CACHE_TTL)
        return resp

    async def get_by_employee_cached(
        self, employee_id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherResponse:
        cache_key = f"teacher:employee:{employee_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return TeacherResponse.model_validate(cached)

        teacher = await self.repo.get_by_employee(employee_id)
        if not teacher or teacher.school_id != school_id:
            raise TeacherNotFoundException()

        resp = self.map_to_response(teacher)
        await self.cache.set(cache_key, resp.model_dump(mode="json"), CACHE_TTL)
        return resp
