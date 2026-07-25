import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams
from app.modules.admission.models import Admission, AdmissionSequence, AdmissionTimeline


class AdmissionRepository:
    """
    Admission repository encapsulating persistence, sequence incrementing with
    row-level locking, and paginated searches for Admission records.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_admission(self, admission: Admission) -> Admission:
        """Persists a new admission application."""
        self.session.add(admission)
        return admission

    async def get_admission_by_id(
        self, admission_id: uuid.UUID, include_deleted: bool = False
    ) -> Admission | None:
        """Retrieves an admission record by UUID, eager loading relationships."""
        stmt = select(Admission).where(Admission.id == admission_id)
        if not include_deleted:
            stmt = stmt.where(Admission.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_admission(
        self, admission_id: uuid.UUID, data: dict[str, Any]
    ) -> Admission | None:
        """Updates fields on an existing admission record."""
        admission = await self.get_admission_by_id(admission_id)
        if not admission:
            return None
        for k, v in data.items():
            setattr(admission, k, v)
        self.session.add(admission)
        return admission

    async def get_admission_by_application_number(
        self, school_id: uuid.UUID, app_number: str
    ) -> Admission | None:
        """Looks up an admission application by number unique within a school tenant context."""
        stmt = select(Admission).where(
            Admission.school_id == school_id,
            Admission.application_number == app_number,
            Admission.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_student_id(
        self, school_id: uuid.UUID, student_id: uuid.UUID
    ) -> bool:
        """Checks if a student already has an active admission application context."""
        stmt = select(func.count(Admission.id)).where(
            Admission.school_id == school_id,
            Admission.student_id == student_id,
            Admission.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def paginate(
        self,
        school_id: uuid.UUID,
        params: PageParams,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """Provides paginated, sorted search query filters for admission applications list."""
        stmt = select(Admission).where(Admission.school_id == school_id)
        if not include_deleted:
            stmt = stmt.where(Admission.is_deleted == False)

        # Wildcard Search across application number or student name fields
        if search:
            q = f"%{search}%"
            # Join Student to search by student name
            from app.modules.student.models import Student

            stmt = stmt.join(Student, Admission.student_id == Student.id).where(
                or_(
                    Admission.application_number.ilike(q),
                    Student.first_name.ilike(q),
                    Student.last_name.ilike(q),
                )
            )

        if filters:
            for k, v in filters.items():
                if v is None:
                    continue
                if k == "status":
                    stmt = stmt.where(Admission.status == v)
                elif k == "academic_year":
                    stmt = stmt.where(Admission.academic_year == v)
                elif hasattr(Admission, k):
                    stmt = stmt.where(getattr(Admission, k) == v)

        # Default order by creation date
        stmt = stmt.order_by(Admission.created_at.desc())

        # Total counts
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.session.execute(total_stmt)
        total_records = total_res.scalar_one() or 0

        # Offsets
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
    # Timeline Persistence
    # ==========================================

    async def create_timeline(self, timeline: AdmissionTimeline) -> AdmissionTimeline:
        """Persists a new timeline audit trail entry."""
        self.session.add(timeline)
        return timeline

    # ==========================================
    # Unique Admission Number Sequence Generator
    # ==========================================

    async def get_next_sequence_value(self, school_id: uuid.UUID, year: int) -> str:
        """
        Uses SELECT FOR UPDATE to atomically get and increment the school's sequence number,
        preventing race conditions and duplicates during concurrent admission enrollment.
        """
        stmt = (
            select(AdmissionSequence)
            .where(AdmissionSequence.school_id == school_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        seq = result.scalar_one_or_none()

        if not seq:
            # First time initialization for this school
            seq = AdmissionSequence(
                school_id=school_id,
                prefix="SCH",
                current_value=0,
            )
            self.session.add(seq)
            await self.session.flush()

        seq.current_value += 1
        self.session.add(seq)
        await self.session.flush()

        # Format prefix-year-000000 (padded to 6 digits)
        formatted_sequence = f"{seq.prefix}-{year}-{seq.current_value:06d}"
        return formatted_sequence

    async def configure_sequence_prefix(
        self, school_id: uuid.UUID, prefix: str
    ) -> None:
        """Configures sequence prefix for a school."""
        stmt = (
            select(AdmissionSequence)
            .where(AdmissionSequence.school_id == school_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        seq = result.scalar_one_or_none()

        if not seq:
            seq = AdmissionSequence(school_id=school_id, prefix=prefix, current_value=0)
        else:
            seq.prefix = prefix
        self.session.add(seq)
        await self.session.flush()
