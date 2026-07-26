import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.term.enums import TermStatus
from app.modules.term.exceptions import (
    InvalidTermDataException,
    OverlappingTermException,
    TermNotFoundException,
)
from app.modules.term.models import Term
from app.modules.term.repository import TermRepository
from app.modules.term.schemas import TermCreate, TermUpdate
from app.modules.term.validators import validate_containment, validate_dates


class TermService:
    """
    Service class orchestrating business actions and validations for Terms/Semesters.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TermRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID
    ) -> None:
        """Helper to clear cached term entries for the school/academic year context."""
        await self.cache.delete(f"term:active:{academic_year_id}")
        await self.cache.delete(f"term:default:{academic_year_id}")
        await self.cache.delete(f"term:list:{academic_year_id}")
        await self.cache.delete_pattern(f"term:search:{school_id}*")
        await self.cache.delete_pattern(f"academic_dashboard:*:{school_id}*")

    async def create_term(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TermCreate,
    ) -> Term:
        # 1. Verify school status
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidTermDataException("School does not exist or is inactive.")

        # 2. Verify academic year status
        ay = await self.db.get(AcademicYear, data.academic_year_id)
        if not ay or ay.school_id != school_id or ay.is_deleted:
            raise InvalidTermDataException(
                "Academic Year does not exist or is deleted."
            )
        if ay.status == AcademicYearStatus.ARCHIVED:
            raise InvalidTermDataException(
                "Cannot create terms within an archived Academic Year."
            )

        # 3. Validate dates order
        validate_dates(data.start_date, data.end_date)

        # 4. Validate containment
        validate_containment(data.start_date, data.end_date, ay.start_date, ay.end_date)

        # 5. Validate code uniqueness per school
        conflict_code = await self.repo.get_by_code(school_id, data.code)
        if conflict_code:
            raise InvalidTermDataException(
                f"Term with code '{data.code}' already exists."
            )

        # 6. Validate name uniqueness per academic year
        conflict_name = await self.repo.get_by_name(data.academic_year_id, data.name)
        if conflict_name:
            raise InvalidTermDataException(
                f"Term with name '{data.name}' already exists."
            )

        # 7. Check overlapping terms
        overlap = await self.repo.check_overlapping(
            data.academic_year_id, data.start_date, data.end_date
        )
        if overlap:
            raise OverlappingTermException()

        term = Term(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            code=data.code,
            description=data.description,
            term_number=data.term_number,
            start_date=data.start_date,
            end_date=data.end_date,
            is_active=False,
            is_default=False,
            is_locked=False,
            status=TermStatus.PLANNED,
            created_by=user_id,
        )

        await self.repo.create(term)
        await self.db.flush()

        # Invalidate Cache
        await self._invalidate_cache(school_id, data.academic_year_id)

        # Audit Log
        await self.audit.log_action(
            module="term",
            action="create",
            entity_name="Term",
            entity_id=term.id,
            metadata_json={"code": data.code, "name": data.name},
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def update_term(
        self,
        term_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TermUpdate,
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        # Cannot modify locked term
        if term.is_locked:
            raise InvalidTermDataException("Cannot modify locked Term.")

        # Validate name uniqueness if changed
        if data.name and data.name != term.name:
            conflict_name = await self.repo.get_by_name(
                term.academic_year_id, data.name
            )
            if conflict_name:
                raise InvalidTermDataException(
                    f"Term with name '{data.name}' already exists."
                )
            term.name = data.name

        # Validate code uniqueness if changed
        if data.code and data.code != term.code:
            conflict_code = await self.repo.get_by_code(school_id, data.code)
            if conflict_code:
                raise InvalidTermDataException(
                    f"Term with code '{data.code}' already exists."
                )
            term.code = data.code

        # Validate term sequential number if changed
        if data.term_number is not None:
            term.term_number = data.term_number

        # Validate date modifications
        start = data.start_date or term.start_date
        end = data.end_date or term.end_date
        validate_dates(start, end)

        # Ensure dates are still within the Academic Year boundary
        ay = await self.db.get(AcademicYear, term.academic_year_id)
        assert ay is not None
        validate_containment(start, end, ay.start_date, ay.end_date)

        if data.start_date or data.end_date:
            overlap = await self.repo.check_overlapping(
                term.academic_year_id, start, end, exclude_id=term_id
            )
            if overlap:
                raise OverlappingTermException()
            term.start_date = start
            term.end_date = end

        if data.description is not None:
            term.description = data.description

        term.updated_by = user_id
        await self.repo.update(term)
        await self.db.flush()

        await self._invalidate_cache(school_id, term.academic_year_id)

        await self.audit.log_action(
            module="term",
            action="update",
            entity_name="Term",
            entity_id=term.id,
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def delete_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        # Cannot delete active Term
        if term.status == TermStatus.ACTIVE:
            raise InvalidTermDataException("Cannot delete active Term.")

        res = await self.repo.delete(term_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, term.academic_year_id)
            await self.audit.log_action(
                module="term",
                action="delete",
                entity_name="Term",
                entity_id=term_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def restore_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        term = await self.repo.get_by_id(term_id, include_deleted=True)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        res = await self.repo.restore(term_id)
        if res:
            await self.db.flush()
            await self._invalidate_cache(school_id, term.academic_year_id)
            await self.audit.log_action(
                module="term",
                action="restore",
                entity_name="Term",
                entity_id=term_id,
                user_id=user_id,
                school_id=school_id,
            )
        return res

    async def activate_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        # Cannot activate archived term
        if term.status == TermStatus.ARCHIVED:
            raise InvalidTermDataException("Cannot activate archived Term.")

        # Deactivate other active terms in the same academic year
        other_active = await self.repo.list_other_active_terms(
            term.academic_year_id, term_id
        )
        for ot in other_active:
            ot.status = TermStatus.COMPLETED
            ot.is_active = False
            await self.repo.update(ot)

        term.status = TermStatus.ACTIVE
        term.is_active = True
        await self.repo.update(term)
        await self.db.flush()

        await self._invalidate_cache(school_id, term.academic_year_id)

        await self.audit.log_action(
            module="term",
            action="activate",
            entity_name="Term",
            entity_id=term_id,
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def deactivate_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        if term.status == TermStatus.ACTIVE:
            term.status = TermStatus.COMPLETED
            term.is_active = False
            await self.repo.update(term)
            await self.db.flush()

            await self._invalidate_cache(school_id, term.academic_year_id)
            await self.audit.log_action(
                module="term",
                action="deactivate",
                entity_name="Term",
                entity_id=term_id,
                user_id=user_id,
                school_id=school_id,
            )

        return term

    async def set_default_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        # Clear other default terms in the same academic year
        other_defaults = await self.repo.list_other_default_terms(
            term.academic_year_id, term_id
        )
        for od in other_defaults:
            od.is_default = False
            await self.repo.update(od)

        term.is_default = True
        await self.repo.update(term)
        await self.db.flush()

        await self._invalidate_cache(school_id, term.academic_year_id)

        await self.audit.log_action(
            module="term",
            action="set_default",
            entity_name="Term",
            entity_id=term_id,
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def lock_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        term.is_locked = True
        await self.repo.update(term)
        await self.db.flush()

        await self._invalidate_cache(school_id, term.academic_year_id)

        await self.audit.log_action(
            module="term",
            action="lock",
            entity_name="Term",
            entity_id=term_id,
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def unlock_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        term.is_locked = False
        await self.repo.update(term)
        await self.db.flush()

        await self._invalidate_cache(school_id, term.academic_year_id)

        await self.audit.log_action(
            module="term",
            action="unlock",
            entity_name="Term",
            entity_id=term_id,
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def archive_term(
        self, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> Term:
        term = await self.repo.get_by_id(term_id)
        if not term or term.school_id != school_id:
            raise TermNotFoundException()

        term.status = TermStatus.ARCHIVED
        term.is_active = False
        await self.repo.update(term)
        await self.db.flush()

        await self._invalidate_cache(school_id, term.academic_year_id)

        await self.audit.log_action(
            module="term",
            action="archive",
            entity_name="Term",
            entity_id=term_id,
            user_id=user_id,
            school_id=school_id,
        )

        return term

    async def get_active_cached(self, academic_year_id: uuid.UUID) -> Term | None:
        cache_key = f"term:active:{academic_year_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return Term(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                academic_year_id=uuid.UUID(cached["academic_year_id"]),
                name=cached["name"],
                code=cached["code"],
                description=cached["description"],
                term_number=cached["term_number"],
                start_date=date.fromisoformat(cached["start_date"]),
                end_date=date.fromisoformat(cached["end_date"]),
                is_active=cached["is_active"],
                is_default=cached["is_default"],
                is_locked=cached["is_locked"],
                status=TermStatus(cached["status"]),
                created_by=uuid.UUID(cached["created_by"])
                if cached.get("created_by")
                else None,
                updated_by=uuid.UUID(cached["updated_by"])
                if cached.get("updated_by")
                else None,
            )

        term = await self.repo.get_active(academic_year_id)
        if term:
            state_dict = {
                "id": str(term.id),
                "school_id": str(term.school_id),
                "academic_year_id": str(term.academic_year_id),
                "name": term.name,
                "code": term.code,
                "description": term.description,
                "term_number": term.term_number,
                "start_date": term.start_date.isoformat(),
                "end_date": term.end_date.isoformat(),
                "is_active": term.is_active,
                "is_default": term.is_default,
                "is_locked": term.is_locked,
                "status": term.status.value,
                "created_by": str(term.created_by) if term.created_by else None,
                "updated_by": str(term.updated_by) if term.updated_by else None,
            }
            await self.cache.set(cache_key, state_dict, 3600)
        return term

    async def get_default_cached(self, academic_year_id: uuid.UUID) -> Term | None:
        cache_key = f"term:default:{academic_year_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return Term(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                academic_year_id=uuid.UUID(cached["academic_year_id"]),
                name=cached["name"],
                code=cached["code"],
                description=cached["description"],
                term_number=cached["term_number"],
                start_date=date.fromisoformat(cached["start_date"]),
                end_date=date.fromisoformat(cached["end_date"]),
                is_active=cached["is_active"],
                is_default=cached["is_default"],
                is_locked=cached["is_locked"],
                status=TermStatus(cached["status"]),
                created_by=uuid.UUID(cached["created_by"])
                if cached.get("created_by")
                else None,
                updated_by=uuid.UUID(cached["updated_by"])
                if cached.get("updated_by")
                else None,
            )

        term = await self.repo.get_default(academic_year_id)
        if term:
            state_dict = {
                "id": str(term.id),
                "school_id": str(term.school_id),
                "academic_year_id": str(term.academic_year_id),
                "name": term.name,
                "code": term.code,
                "description": term.description,
                "term_number": term.term_number,
                "start_date": term.start_date.isoformat(),
                "end_date": term.end_date.isoformat(),
                "is_active": term.is_active,
                "is_default": term.is_default,
                "is_locked": term.is_locked,
                "status": term.status.value,
                "created_by": str(term.created_by) if term.created_by else None,
                "updated_by": str(term.updated_by) if term.updated_by else None,
            }
            await self.cache.set(cache_key, state_dict, 3600)
        return term

    async def get_by_academic_year_cached(
        self, academic_year_id: uuid.UUID
    ) -> list[Term]:
        cache_key = f"term:list:{academic_year_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [
                Term(
                    id=uuid.UUID(t["id"]),
                    school_id=uuid.UUID(t["school_id"]),
                    academic_year_id=uuid.UUID(t["academic_year_id"]),
                    name=t["name"],
                    code=t["code"],
                    description=t["description"],
                    term_number=t["term_number"],
                    start_date=date.fromisoformat(t["start_date"]),
                    end_date=date.fromisoformat(t["end_date"]),
                    is_active=t["is_active"],
                    is_default=t["is_default"],
                    is_locked=t["is_locked"],
                    status=TermStatus(t["status"]),
                    created_by=uuid.UUID(t["created_by"])
                    if t.get("created_by")
                    else None,
                    updated_by=uuid.UUID(t["updated_by"])
                    if t.get("updated_by")
                    else None,
                )
                for t in cached
            ]

        terms = await self.repo.get_by_academic_year(academic_year_id)
        state_list = [
            {
                "id": str(t.id),
                "school_id": str(t.school_id),
                "academic_year_id": str(t.academic_year_id),
                "name": t.name,
                "code": t.code,
                "description": t.description,
                "term_number": t.term_number,
                "start_date": t.start_date.isoformat(),
                "end_date": t.end_date.isoformat(),
                "is_active": t.is_active,
                "is_default": t.is_default,
                "is_locked": t.is_locked,
                "status": t.status.value,
                "created_by": str(t.created_by) if t.created_by else None,
                "updated_by": str(t.updated_by) if t.updated_by else None,
            }
            for t in terms
        ]
        await self.cache.set(cache_key, state_list, 3600)
        return terms
