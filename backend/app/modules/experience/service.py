import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.modules.employee.models import Employee
from app.modules.experience.constants import CACHE_TTL
from app.modules.experience.enums import ExperienceStatus
from app.modules.experience.exceptions import (
    ExperienceNotFoundException,
    InvalidExperienceException,
)
from app.modules.experience.models import Experience
from app.modules.experience.repository import ExperienceRepository
from app.modules.experience.schemas import (
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
)
from app.modules.experience.validators import (
    validate_experience_dates,
    validate_experience_durations,
    validate_manager_email,
    validate_manager_phone,
    validate_required_fields,
    validate_salary,
)


class ExperienceService:
    """
    Service layer orchestrating business logic and workflows for Professional Experience records.
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = ExperienceRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    def map_to_response(self, exp: Experience) -> ExperienceResponse:
        return ExperienceResponse.model_validate(exp)

    async def _invalidate_cache(
        self, exp_id: uuid.UUID, employee_id: uuid.UUID
    ) -> None:
        """Invalidates related caching keys."""
        await self.cache.delete(f"experience:details:{exp_id}")
        await self.cache.delete(f"experience:employee:{employee_id}")
        await self.cache.delete_pattern("experience:list:*")

    async def create_experience(
        self, data: ExperienceCreate, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        # 1. Validation checks
        validate_required_fields(
            data.organization_name, data.designation, data.start_date
        )
        validate_experience_dates(
            data.start_date, data.end_date, data.currently_working
        )
        validate_experience_durations(data.experience_years, data.experience_months)
        validate_salary(data.salary)
        validate_manager_email(data.manager_email)
        validate_manager_phone(data.manager_phone)

        # Check employee
        emp = await self.db.get(Employee, data.employee_id)
        if not emp or emp.is_deleted or emp.school_id != school_id:
            raise InvalidExperienceException(
                "Employee not found or belongs to another school"
            )

        # 2. Create record
        exp = Experience(
            school_id=school_id,
            employee_id=data.employee_id,
            employment_type=data.employment_type,
            organization_name=data.organization_name,
            organization_type=data.organization_type,
            designation=data.designation,
            department=data.department,
            employment_category=data.employment_category,
            start_date=data.start_date,
            end_date=data.end_date,
            currently_working=data.currently_working,
            experience_years=data.experience_years or 0,
            experience_months=data.experience_months or 0,
            salary=data.salary,
            currency=data.currency,
            reason_for_leaving=data.reason_for_leaving,
            responsibilities=data.responsibilities,
            achievements=data.achievements,
            skills_used=data.skills_used,
            manager_name=data.manager_name,
            manager_email=data.manager_email,
            manager_phone=data.manager_phone,
            reference_available=data.reference_available,
            experience_certificate_url=data.experience_certificate_url,
            remarks=data.remarks,
            created_by=user_id,
            updated_by=user_id,
        )

        await self.repo.create(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, data.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="create",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def update_experience(
        self,
        exp_id: uuid.UUID,
        data: ExperienceUpdate,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        # Reject update on locked record
        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        # Validate updates if fields are set
        if (
            data.organization_name is not None
            or data.designation is not None
            or data.start_date is not None
        ):
            org = (
                data.organization_name
                if data.organization_name is not None
                else exp.organization_name
            )
            desg = data.designation if data.designation is not None else exp.designation
            start = data.start_date if data.start_date is not None else exp.start_date
            validate_required_fields(org, desg, start)

        start_date = data.start_date if data.start_date is not None else exp.start_date
        end_date = data.end_date if data.end_date is not None else exp.end_date
        currently_working = (
            data.currently_working
            if data.currently_working is not None
            else exp.currently_working
        )
        validate_experience_dates(start_date, end_date, currently_working)

        years = (
            data.experience_years
            if data.experience_years is not None
            else exp.experience_years
        )
        months = (
            data.experience_months
            if data.experience_months is not None
            else exp.experience_months
        )
        validate_experience_durations(years, months)

        salary = data.salary if data.salary is not None else exp.salary
        validate_salary(salary)

        if data.manager_email is not None:
            validate_manager_email(data.manager_email)
        if data.manager_phone is not None:
            validate_manager_phone(data.manager_phone)

        # Apply properties
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(exp, k, v)

        exp.updated_by = user_id

        await self.repo.update(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="update",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def delete_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        await self.repo.delete(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="delete",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def restore_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id, include_deleted=True)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        await self.repo.restore(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="restore",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def activate_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        if exp.status == ExperienceStatus.ARCHIVED:
            raise InvalidExperienceException("Cannot activate archived experience")

        await self.repo.activate(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="activate",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def deactivate_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        await self.repo.deactivate(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="deactivate",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def lock_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        await self.repo.lock(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="lock",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def unlock_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        await self.repo.unlock(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="unlock",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def archive_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        await self.repo.archive(exp)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="archive",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def verify_experience(
        self, exp_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Experience:
        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        if exp.is_locked:
            raise InvalidExperienceException("Cannot modify locked experience")

        await self.repo.verify(exp, user_id)
        await self.db.flush()

        await self._invalidate_cache(exp.id, exp.employee_id)

        # Audit
        await self.audit.log_action(
            module="experience",
            action="verify",
            entity_name="Experience",
            entity_id=exp.id,
            user_id=user_id,
            school_id=school_id,
        )

        return exp

    async def calculate_total_experience(
        self, employee_id: uuid.UUID, school_id: uuid.UUID
    ) -> dict[str, int]:
        """Sums up the years and months of all verified experience records for an employee."""
        # Check employee exists in school
        emp = await self.db.get(Employee, employee_id)
        if not emp or emp.is_deleted or emp.school_id != school_id:
            raise InvalidExperienceException(
                "Employee not found or belongs to another school"
            )

        records = await self.repo.get_verified_experiences(employee_id)
        total_yrs = 0
        total_mths = 0
        for r in records:
            total_yrs += r.experience_years or 0
            total_mths += r.experience_months or 0

        extra_years = total_mths // 12
        remaining_months = total_mths % 12
        final_years = total_yrs + extra_years

        return {
            "total_years": final_years,
            "total_months": remaining_months,
        }

    async def get_by_id_cached(
        self, exp_id: uuid.UUID, school_id: uuid.UUID
    ) -> ExperienceResponse:
        cache_key = f"experience:details:{exp_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ExperienceResponse.model_validate(cached)

        exp = await self.repo.get_by_id(exp_id)
        if not exp or exp.school_id != school_id:
            raise ExperienceNotFoundException()

        resp = self.map_to_response(exp)
        await self.cache.set(cache_key, resp.model_dump(mode="json"), CACHE_TTL)
        return resp

    async def get_by_employee_cached(
        self, employee_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[ExperienceResponse]:
        cache_key = f"experience:employee:{employee_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [ExperienceResponse.model_validate(x) for x in cached]

        items = await self.repo.get_by_employee(school_id, employee_id)
        resp_list = [self.map_to_response(item) for item in items]
        await self.cache.set(
            cache_key, [r.model_dump(mode="json") for r in resp_list], CACHE_TTL
        )
        return resp_list
