import builtins
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.common.pagination import PageParams, paginate_by_page
from app.modules.student.models import Student


class StudentRepository:
    """
    Repository class encapsulating database query actions for the Student model.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, student: Student) -> Student:
        """Persists a new student record to the database."""
        self.session.add(student)
        return student

    async def update(self, student: Student) -> Student:
        """Updates a student record."""
        self.session.add(student)
        return student

    async def delete(self, student_id: uuid.UUID) -> bool:
        """Performs a soft delete of a student by toggling is_deleted flag."""
        student = await self.get_by_id(student_id, include_deleted=True)
        if student and not student.is_deleted:
            student.is_deleted = True
            student.deleted_at = datetime.now(UTC)
            self.session.add(student)
            return True
        return False

    async def restore(self, student_id: uuid.UUID) -> bool:
        """Restores a soft-deleted student back to active status."""
        student = await self.get_by_id(student_id, include_deleted=True)
        if student and student.is_deleted:
            student.is_deleted = False
            student.deleted_at = None
            self.session.add(student)
            return True
        return False

    async def get_by_id(
        self, student_id: uuid.UUID, include_deleted: bool = False
    ) -> Student | None:
        """Retrieves a student record by its UUID."""
        stmt = select(Student).where(Student.id == student_id)
        if not include_deleted:
            stmt = stmt.where(Student.is_deleted == False)
        result = await self.session.execute(stmt)
        student = result.scalar_one_or_none()
        return student if isinstance(student, Student) else None

    async def get_by_admission_number(
        self, school_id: uuid.UUID, admission_number: str, include_deleted: bool = False
    ) -> Student | None:
        """Retrieves a student record by admission number within school tenant context."""
        stmt = select(Student).where(
            Student.school_id == school_id,
            Student.admission_number == admission_number,
        )
        if not include_deleted:
            stmt = stmt.where(Student.is_deleted == False)
        result = await self.session.execute(stmt)
        student = result.scalar_one_or_none()
        return student if isinstance(student, Student) else None

    async def list(
        self,
        school_id: uuid.UUID,
        filters: dict[str, Any] | None = None,
        include_deleted: bool = False,
    ) -> list[Student]:
        """Lists students matching criteria within school tenant context."""
        stmt = select(Student).where(Student.school_id == school_id)
        if not include_deleted:
            stmt = stmt.where(Student.is_deleted == False)

        if filters:
            for key, val in filters.items():
                if val is not None and hasattr(Student, key):
                    stmt = stmt.where(getattr(Student, key) == val)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        school_id: uuid.UUID,
        query: str,
        include_deleted: bool = False,
    ) -> builtins.list[Student]:
        """Searches student by name, email, or admission number."""
        stmt = select(Student).where(Student.school_id == school_id)
        if not include_deleted:
            stmt = stmt.where(Student.is_deleted == False)

        term = f"%{query}%"
        stmt = stmt.where(
            or_(
                Student.first_name.ilike(term),
                Student.middle_name.ilike(term),
                Student.last_name.ilike(term),
                Student.admission_number.ilike(term),
                Student.email.ilike(term),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists_by_admission_number(
        self, school_id: uuid.UUID, admission_number: str
    ) -> bool:
        """Checks if admission number is already in use by active student in school tenant context."""
        stmt = select(func.count(Student.id)).where(
            Student.school_id == school_id,
            Student.admission_number == admission_number,
            Student.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def exists_by_email(self, school_id: uuid.UUID, email: str) -> bool:
        """Checks if email is already in use by active student in school tenant context."""
        stmt = select(func.count(Student.id)).where(
            Student.school_id == school_id,
            Student.email == email,
            Student.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def count_students(
        self, school_id: uuid.UUID, include_deleted: bool = False
    ) -> int:
        """Returns the total number of students within school tenant context."""
        stmt = select(func.count(Student.id)).where(Student.school_id == school_id)
        if not include_deleted:
            stmt = stmt.where(Student.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def paginate(
        self,
        school_id: uuid.UUID,
        params: PageParams,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """Returns paginated query page for students supporting search, dynamic filtering, and sorting."""
        stmt = select(Student).where(Student.school_id == school_id)
        if not include_deleted:
            stmt = stmt.where(Student.is_deleted == False)

        # 1. Advanced Search
        if search:
            term = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Student.first_name.ilike(term),
                    Student.middle_name.ilike(term),
                    Student.last_name.ilike(term),
                    Student.admission_number.ilike(term),
                    Student.roll_number.ilike(term),
                    Student.email.ilike(term),
                    Student.phone.ilike(term),
                )
            )

        # 2. Dynamic Filtering
        if filters:
            for key, val in filters.items():
                if val is None:
                    continue
                # Date ranges
                if key == "joined_date_from":
                    stmt = stmt.where(Student.joined_date >= val)
                elif key == "joined_date_to":
                    stmt = stmt.where(Student.joined_date <= val)
                elif key == "created_at_from":
                    stmt = stmt.where(Student.created_at >= val)
                elif key == "created_at_to":
                    stmt = stmt.where(Student.created_at <= val)
                elif key == "updated_at_from":
                    stmt = stmt.where(Student.updated_at >= val)
                elif key == "updated_at_to":
                    stmt = stmt.where(Student.updated_at <= val)
                # Future placeholders
                elif key in ("class_id", "section_id"):
                    if hasattr(Student, key):
                        stmt = stmt.where(getattr(Student, key) == val)
                # Exact match
                elif hasattr(Student, key):
                    stmt = stmt.where(getattr(Student, key) == val)

        # 3. Sorting
        from app.common.sorting import apply_sorting

        sortable = [
            "first_name",
            "last_name",
            "admission_number",
            "joined_date",
            "created_at",
            "updated_at",
        ]
        stmt = apply_sorting(stmt, Student, sort, sortable, default_sort="-created_at")

        return await paginate_by_page(self.session, stmt, params)
