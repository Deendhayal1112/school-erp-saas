import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.modules.student_assignment.enums import AssignmentStatus
from app.modules.student_assignment.models import StudentAcademicAssignment


class StudentAcademicAssignmentRepository:
    """
    Repository class encapsulating database query operations for Student Academic Assignments.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(
        self, assignment: StudentAcademicAssignment
    ) -> StudentAcademicAssignment:
        """Persists a new assignment record in database."""
        self.session.add(assignment)
        return assignment

    async def update(
        self, assignment: StudentAcademicAssignment
    ) -> StudentAcademicAssignment:
        """Updates an existing assignment record."""
        self.session.add(assignment)
        return assignment

    async def delete(self, assignment_id: uuid.UUID) -> bool:
        """Performs soft-delete of assignment record."""
        assignment = await self.get_by_id(assignment_id, include_deleted=True)
        if assignment and not assignment.is_deleted:
            assignment.is_deleted = True
            assignment.deleted_at = datetime.now(UTC)
            self.session.add(assignment)
            return True
        return False

    async def restore(self, assignment_id: uuid.UUID) -> bool:
        """Restores a soft-deleted assignment record."""
        assignment = await self.get_by_id(assignment_id, include_deleted=True)
        if assignment and assignment.is_deleted:
            assignment.is_deleted = False
            assignment.deleted_at = None
            self.session.add(assignment)
            return True
        return False

    async def get_by_id(
        self, assignment_id: uuid.UUID, include_deleted: bool = False
    ) -> StudentAcademicAssignment | None:
        """Retrieves assignment record by UUID."""
        stmt = select(StudentAcademicAssignment).where(
            StudentAcademicAssignment.id == assignment_id
        )
        if not include_deleted:
            stmt = stmt.where(StudentAcademicAssignment.is_deleted == False)
        result = await self.session.execute(stmt)
        assignment = result.scalar_one_or_none()
        return assignment if isinstance(assignment, StudentAcademicAssignment) else None

    async def get_by_student(
        self, student_id: uuid.UUID, include_deleted: bool = False
    ) -> list[StudentAcademicAssignment]:
        """Retrieves list of all assignments associated with a student."""
        stmt = select(StudentAcademicAssignment).where(
            StudentAcademicAssignment.student_id == student_id
        )
        if not include_deleted:
            stmt = stmt.where(StudentAcademicAssignment.is_deleted == False)
        stmt = stmt.order_by(StudentAcademicAssignment.joined_on.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_student(
        self, student_id: uuid.UUID
    ) -> StudentAcademicAssignment | None:
        """Retrieves the single active assignment associated with a student."""
        stmt = (
            select(StudentAcademicAssignment)
            .where(StudentAcademicAssignment.student_id == student_id)
            .where(StudentAcademicAssignment.status == AssignmentStatus.ACTIVE)
            .where(StudentAcademicAssignment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        assignment = result.scalar_one_or_none()
        return assignment if isinstance(assignment, StudentAcademicAssignment) else None

    async def get_by_class(
        self, class_id: uuid.UUID, include_deleted: bool = False
    ) -> list[StudentAcademicAssignment]:
        """Retrieves assignments belonging to a class."""
        stmt = select(StudentAcademicAssignment).where(
            StudentAcademicAssignment.class_id == class_id
        )
        if not include_deleted:
            stmt = stmt.where(StudentAcademicAssignment.is_deleted == False)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_section(
        self, section_id: uuid.UUID, include_deleted: bool = False
    ) -> list[StudentAcademicAssignment]:
        """Retrieves assignments belonging to a section."""
        stmt = select(StudentAcademicAssignment).where(
            StudentAcademicAssignment.section_id == section_id
        )
        if not include_deleted:
            stmt = stmt.where(StudentAcademicAssignment.is_deleted == False)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_roll_number(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID | None,
        roll_number: str,
    ) -> StudentAcademicAssignment | None:
        """Looks up assignment matching unique school section roll number context."""
        stmt = (
            select(StudentAcademicAssignment)
            .where(StudentAcademicAssignment.school_id == school_id)
            .where(StudentAcademicAssignment.academic_year_id == academic_year_id)
            .where(StudentAcademicAssignment.class_id == class_id)
            .where(StudentAcademicAssignment.section_id == section_id)
            .where(StudentAcademicAssignment.roll_number == roll_number)
            .where(StudentAcademicAssignment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        assignment = result.scalar_one_or_none()
        return assignment if isinstance(assignment, StudentAcademicAssignment) else None
