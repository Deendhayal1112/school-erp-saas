import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.modules.employee.models import Employee
from app.modules.qualification.constants import CACHE_TTL
from app.modules.qualification.enums import QualificationStatus
from app.modules.qualification.exceptions import (
    InvalidQualificationException,
    QualificationNotFoundException,
)
from app.modules.qualification.models import Qualification
from app.modules.qualification.repository import QualificationRepository
from app.modules.qualification.schemas import (
    QualificationCreate,
    QualificationResponse,
    QualificationUpdate,
)
from app.modules.qualification.validators import (
    validate_cgpa,
    validate_passing_year,
    validate_percentage,
    validate_qualification_dates,
    validate_required_fields,
    validate_validity_dates,
)


class QualificationService:
    """
    Service layer orchestrating business logic and workflows for Qualification records.
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = QualificationRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    def map_to_response(self, q: Qualification) -> QualificationResponse:
        return QualificationResponse.model_validate(q)

    async def _invalidate_cache(self, q_id: uuid.UUID, employee_id: uuid.UUID) -> None:
        """Invalidates related caching keys."""
        await self.cache.delete(f"qualification:details:{q_id}")
        await self.cache.delete(f"qualification:employee:{employee_id}")
        await self.cache.delete_pattern("qualification:list:*")

    async def create_qualification(
        self, data: QualificationCreate, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        # 1. Validation checks
        validate_required_fields(data.qualification_name, data.institution_name)
        validate_qualification_dates(data.start_date, data.end_date)
        validate_validity_dates(data.valid_from, data.valid_until)
        validate_cgpa(data.cgpa, data.cgpa_scale)
        validate_percentage(data.percentage)
        validate_passing_year(data.passing_year)

        # Check employee
        emp = await self.db.get(Employee, data.employee_id)
        if not emp or emp.is_deleted or emp.school_id != school_id:
            raise InvalidQualificationException(
                "Employee not found or belongs to another school"
            )

        # 2. Highest qualification logic
        if data.is_highest_qualification:
            await self.repo.reset_highest_qualification_except(data.employee_id)

        # 3. Create record
        q = Qualification(
            school_id=school_id,
            employee_id=data.employee_id,
            qualification_type=data.qualification_type,
            qualification_name=data.qualification_name,
            degree=data.degree,
            specialization=data.specialization,
            institution_name=data.institution_name,
            board_or_university=data.board_or_university,
            country=data.country,
            state=data.state,
            city=data.city,
            mode_of_study=data.mode_of_study,
            grade=data.grade,
            percentage=data.percentage,
            cgpa=data.cgpa,
            cgpa_scale=data.cgpa_scale,
            passing_year=data.passing_year,
            start_date=data.start_date,
            end_date=data.end_date,
            certificate_number=data.certificate_number,
            issuing_authority=data.issuing_authority,
            license_number=data.license_number,
            valid_from=data.valid_from,
            valid_until=data.valid_until,
            is_highest_qualification=data.is_highest_qualification,
            document_url=data.document_url,
            remarks=data.remarks,
            created_by=user_id,
            updated_by=user_id,
        )

        await self.repo.create(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, data.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="create",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def update_qualification(
        self,
        q_id: uuid.UUID,
        data: QualificationUpdate,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        # Reject update on locked profile
        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        # Validate updates if fields are set
        if data.qualification_name is not None or data.institution_name is not None:
            name = (
                data.qualification_name
                if data.qualification_name is not None
                else q.qualification_name
            )
            inst = (
                data.institution_name
                if data.institution_name is not None
                else q.institution_name
            )
            validate_required_fields(name, inst)

        start = data.start_date if data.start_date is not None else q.start_date
        end = data.end_date if data.end_date is not None else q.end_date
        validate_qualification_dates(start, end)

        valid_from = data.valid_from if data.valid_from is not None else q.valid_from
        valid_until = (
            data.valid_until if data.valid_until is not None else q.valid_until
        )
        validate_validity_dates(valid_from, valid_until)

        cgpa = data.cgpa if data.cgpa is not None else q.cgpa
        cgpa_scale = data.cgpa_scale if data.cgpa_scale is not None else q.cgpa_scale
        validate_cgpa(cgpa, cgpa_scale)

        if data.percentage is not None:
            validate_percentage(data.percentage)
        if data.passing_year is not None:
            validate_passing_year(data.passing_year)

        # Highest qualification logic
        if data.is_highest_qualification:
            await self.repo.reset_highest_qualification_except(
                q.employee_id, except_q_id=q.id
            )

        # Apply properties
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(q, k, v)

        q.updated_by = user_id

        await self.repo.update(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="update",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def delete_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        await self.repo.delete(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="delete",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def restore_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id, include_deleted=True)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        await self.repo.restore(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="restore",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def activate_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        if q.status == QualificationStatus.ARCHIVED:
            raise InvalidQualificationException(
                "Cannot activate archived qualification"
            )

        await self.repo.activate(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="activate",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def deactivate_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        await self.repo.deactivate(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="deactivate",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def lock_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        await self.repo.lock(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="lock",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def unlock_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        await self.repo.unlock(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="unlock",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def archive_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        await self.repo.archive(q)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="archive",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def verify_qualification(
        self, q_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID
    ) -> Qualification:
        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        if q.is_locked:
            raise InvalidQualificationException("Cannot modify locked qualification")

        await self.repo.verify(q, user_id)
        await self.db.flush()

        await self._invalidate_cache(q.id, q.employee_id)

        # Audit
        await self.audit.log_action(
            module="qualification",
            action="verify",
            entity_name="Qualification",
            entity_id=q.id,
            user_id=user_id,
            school_id=school_id,
        )

        return q

    async def get_by_id_cached(
        self, q_id: uuid.UUID, school_id: uuid.UUID
    ) -> QualificationResponse:
        cache_key = f"qualification:details:{q_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return QualificationResponse.model_validate(cached)

        q = await self.repo.get_by_id(q_id)
        if not q or q.school_id != school_id:
            raise QualificationNotFoundException()

        resp = self.map_to_response(q)
        await self.cache.set(cache_key, resp.model_dump(mode="json"), CACHE_TTL)
        return resp

    async def get_by_employee_cached(
        self, employee_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[QualificationResponse]:
        cache_key = f"qualification:employee:{employee_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [QualificationResponse.model_validate(x) for x in cached]

        items = await self.repo.get_by_employee(school_id, employee_id)
        resp_list = [self.map_to_response(item) for item in items]
        await self.cache.set(
            cache_key, [r.model_dump(mode="json") for r in resp_list], CACHE_TTL
        )
        return resp_list
