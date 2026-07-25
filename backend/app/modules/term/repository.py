import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


class TermRepository:
    """
    Repository class encapsulating database query operations for Terms.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, term: Term) -> Term:
        self.session.add(term)
        return term

    async def update(self, term: Term) -> Term:
        self.session.add(term)
        return term

    async def delete(self, term_id: uuid.UUID) -> bool:
        term = await self.get_by_id(term_id, include_deleted=True)
        if term and not term.is_deleted:
            term.is_deleted = True
            term.deleted_at = datetime.now(UTC)
            self.session.add(term)
            return True
        return False

    async def restore(self, term_id: uuid.UUID) -> bool:
        term = await self.get_by_id(term_id, include_deleted=True)
        if term and term.is_deleted:
            term.is_deleted = False
            term.deleted_at = None
            self.session.add(term)
            return True
        return False

    async def get_by_id(
        self, term_id: uuid.UUID, include_deleted: bool = False
    ) -> Term | None:
        stmt = select(Term).where(Term.id == term_id)
        if not include_deleted:
            stmt = stmt.where(Term.is_deleted == False)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Term) else None

    async def get_by_code(self, school_id: uuid.UUID, code: str) -> Term | None:
        stmt = select(Term).where(
            Term.school_id == school_id,
            Term.code == code,
            Term.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Term) else None

    async def get_by_name(self, academic_year_id: uuid.UUID, name: str) -> Term | None:
        stmt = select(Term).where(
            Term.academic_year_id == academic_year_id,
            Term.name == name,
            Term.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Term) else None

    async def get_active(self, academic_year_id: uuid.UUID) -> Term | None:
        stmt = select(Term).where(
            Term.academic_year_id == academic_year_id,
            Term.status == TermStatus.ACTIVE,
            Term.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Term) else None

    async def get_default(self, academic_year_id: uuid.UUID) -> Term | None:
        stmt = select(Term).where(
            Term.academic_year_id == academic_year_id,
            Term.is_default == True,
            Term.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if isinstance(val, Term) else None

    async def check_overlapping(
        self,
        academic_year_id: uuid.UUID,
        start_date: date,
        end_date: date,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Returns True if there is an overlapping term within the same Academic Year.
        Overlap criteria: (StartA <= EndB) and (EndA >= StartB)
        """
        stmt = select(func.count(Term.id)).where(
            Term.academic_year_id == academic_year_id,
            Term.is_deleted == False,
            Term.start_date <= end_date,
            Term.end_date >= start_date,
        )
        if exclude_id:
            stmt = stmt.where(Term.id != exclude_id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_other_active_terms(
        self, academic_year_id: uuid.UUID, exclude_id: uuid.UUID
    ) -> list[Term]:
        stmt = select(Term).where(
            Term.academic_year_id == academic_year_id,
            Term.id != exclude_id,
            Term.status == TermStatus.ACTIVE,
            Term.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_other_default_terms(
        self, academic_year_id: uuid.UUID, exclude_id: uuid.UUID
    ) -> list[Term]:
        stmt = select(Term).where(
            Term.academic_year_id == academic_year_id,
            Term.id != exclude_id,
            Term.is_default == True,
            Term.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_academic_year(self, academic_year_id: uuid.UUID) -> list[Term]:
        stmt = (
            select(Term)
            .where(
                Term.academic_year_id == academic_year_id,
                Term.is_deleted == False,
            )
            .order_by(Term.term_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        status: TermStatus | None = None,
        name: str | None = None,
        code: str | None = None,
        term_number: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        search: str | None = None,
        sort_by: str | None = "start_date",
        sort_dir: str | None = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Term], int]:
        stmt = select(Term).where(Term.school_id == school_id, Term.is_deleted == False)

        if academic_year_id:
            stmt = stmt.where(Term.academic_year_id == academic_year_id)
        if status:
            stmt = stmt.where(Term.status == status)
        if name:
            stmt = stmt.where(Term.name.ilike(f"%{name}%"))
        if code:
            stmt = stmt.where(Term.code.ilike(f"%{code}%"))
        if term_number is not None:
            stmt = stmt.where(Term.term_number == term_number)
        if start_date:
            stmt = stmt.where(Term.start_date >= start_date)
        if end_date:
            stmt = stmt.where(Term.end_date <= end_date)
        if search:
            stmt = stmt.where(
                or_(
                    Term.name.ilike(f"%{search}%"),
                    Term.code.ilike(f"%{search}%"),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Sorting
        sort_columns = {
            "name": Term.name,
            "start_date": Term.start_date,
            "end_date": Term.end_date,
            "created_at": Term.created_at,
        }
        col = sort_columns.get(sort_by or "start_date", Term.start_date)
        if sort_dir == "desc":
            stmt = stmt.order_by(col.desc())
        else:
            stmt = stmt.order_by(col.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
