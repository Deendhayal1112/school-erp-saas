import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination import PageParams
from app.common.sorting import apply_sorting
from app.modules.guardian.models import Guardian, StudentGuardian


class GuardianRepository:
    """
    Guardian repository encapsulating persistence and lookup queries for
    Guardian records and Student-Guardian mapping associations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, guardian: Guardian) -> Guardian:
        """Persists a new guardian record."""
        self.session.add(guardian)
        return guardian

    async def update(
        self, guardian_id: uuid.UUID, data: dict[str, Any]
    ) -> Guardian | None:
        """Applies field updates to an existing guardian."""
        guardian = await self.get_by_id(guardian_id)
        if not guardian:
            return None
        for k, v in data.items():
            setattr(guardian, k, v)
        self.session.add(guardian)
        return guardian

    async def delete(self, guardian_id: uuid.UUID) -> bool:
        """Performs a soft delete by marking is_deleted=True."""
        guardian = await self.get_by_id(guardian_id)
        if not guardian:
            return False
        guardian.is_deleted = True
        guardian.deleted_at = datetime.utcnow()
        self.session.add(guardian)
        return True

    async def restore(self, guardian_id: uuid.UUID) -> bool:
        """Restores a soft-deleted guardian record."""
        guardian = await self.get_by_id(guardian_id, include_deleted=True)
        if not guardian or not guardian.is_deleted:
            return False
        guardian.is_deleted = False
        guardian.deleted_at = None
        self.session.add(guardian)
        return True

    async def get_by_id(
        self, guardian_id: uuid.UUID, include_deleted: bool = False
    ) -> Guardian | None:
        """Retrieves a guardian record by UUID."""
        stmt = select(Guardian).where(Guardian.id == guardian_id)
        if not include_deleted:
            stmt = stmt.where(Guardian.is_deleted == False)
        result = await self.session.execute(stmt)
        guardian = result.scalar_one_or_none()
        return guardian if isinstance(guardian, Guardian) else None

    async def exists_by_phone(
        self, school_id: uuid.UUID, phone: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Checks if a phone number is registered within the school tenant."""
        stmt = select(func.count(Guardian.id)).where(
            Guardian.school_id == school_id,
            Guardian.phone == phone,
            Guardian.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Guardian.id != exclude_id)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def exists_by_email(
        self, school_id: uuid.UUID, email: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Checks if an email address is registered within the school tenant."""
        stmt = select(func.count(Guardian.id)).where(
            Guardian.school_id == school_id,
            Guardian.email == email,
            Guardian.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Guardian.id != exclude_id)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def exists_by_aadhaar(
        self,
        school_id: uuid.UUID,
        aadhaar_number: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """Checks if an Aadhaar card is registered within the school tenant."""
        stmt = select(func.count(Guardian.id)).where(
            Guardian.school_id == school_id,
            Guardian.aadhaar_number == aadhaar_number,
            Guardian.is_deleted == False,
        )
        if exclude_id:
            stmt = stmt.where(Guardian.id != exclude_id)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def search(self, school_id: uuid.UUID, term: str) -> list[Guardian]:
        """Performs wildcard search across name, contact, and identity fields."""
        q = f"%{term}%"
        stmt = select(Guardian).where(
            Guardian.school_id == school_id,
            Guardian.is_deleted == False,
            or_(
                Guardian.first_name.ilike(q),
                Guardian.middle_name.ilike(q),
                Guardian.last_name.ilike(q),
                Guardian.phone.ilike(q),
                Guardian.email.ilike(q),
                Guardian.aadhaar_number.ilike(q),
            ),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def paginate(
        self,
        school_id: uuid.UUID,
        params: PageParams,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """Provides offset pagination for guardian query lookups."""
        stmt = select(Guardian).where(Guardian.school_id == school_id)
        if not include_deleted:
            stmt = stmt.where(Guardian.is_deleted == False)

        if search:
            q = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Guardian.first_name.ilike(q),
                    Guardian.middle_name.ilike(q),
                    Guardian.last_name.ilike(q),
                    Guardian.phone.ilike(q),
                    Guardian.email.ilike(q),
                    Guardian.aadhaar_number.ilike(q),
                )
            )

        if filters:
            for k, v in filters.items():
                if v is None:
                    continue
                if hasattr(Guardian, k):
                    stmt = stmt.where(getattr(Guardian, k) == v)

        # Sorting
        sortable = ["first_name", "last_name", "phone", "email", "created_at"]
        stmt = apply_sorting(stmt, Guardian, sort, sortable, default_sort="-created_at")

        # Counts & slices
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.session.execute(total_stmt)
        total_records = total_res.scalar_one() or 0

        offset = (params.page - 1) * params.page_size
        stmt = stmt.offset(offset).limit(params.page_size)
        result = await self.session.execute(stmt)
        results = list(result.scalars().all())

        total_pages = (total_records + params.page_size - 1) // params.page_size

        return {
            "results": results,
            "pagination": {
                "total_records": total_records,
                "page": params.page,
                "page_size": params.page_size,
                "total_pages": total_pages,
                "next": None,
                "previous": None,
            },
        }

    # ==========================================
    # Student-Guardian Mapping Persistence Methods
    # ==========================================

    async def create_mapping(self, mapping: StudentGuardian) -> StudentGuardian:
        """Persists a student-guardian mapping association."""
        self.session.add(mapping)
        return mapping

    async def get_mappings_by_student_id(
        self, student_id: uuid.UUID
    ) -> list[StudentGuardian]:
        """Retrieves all active mappings associated with a specific student."""
        stmt = (
            select(StudentGuardian)
            .where(StudentGuardian.student_id == student_id)
            .options(selectinload(StudentGuardian.guardian))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_mapping(
        self, student_id: uuid.UUID, guardian_id: uuid.UUID
    ) -> StudentGuardian | None:
        """Retrieves a single student-guardian mapping record by composite keys."""
        stmt = select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id == guardian_id,
        )
        result = await self.session.execute(stmt)
        mapping = result.scalar_one_or_none()
        return mapping if isinstance(mapping, StudentGuardian) else None

    async def delete_mapping(
        self, student_id: uuid.UUID, guardian_id: uuid.UUID
    ) -> bool:
        """Removes a student-guardian mapping relationship."""
        mapping = await self.get_mapping(student_id, guardian_id)
        if not mapping:
            return False
        await self.session.delete(mapping)
        return True

    async def has_primary_guardian(self, student_id: uuid.UUID) -> bool:
        """Checks if a student already has a mapped primary guardian."""
        stmt = select(func.count(StudentGuardian.student_id)).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.is_primary_guardian == True,
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def unset_primary_guardians(self, student_id: uuid.UUID) -> None:
        """Unsets primary guardian flags for all mapping relationships of a student."""
        stmt = select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.is_primary_guardian == True,
        )
        result = await self.session.execute(stmt)
        for mapping in result.scalars():
            mapping.is_primary_guardian = False
            self.session.add(mapping)
