import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.modules.student_progression.models import StudentProgression


class StudentProgressionRepository:
    """
    Repository class encapsulating database query operations for Student Progressions.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, progression: StudentProgression) -> StudentProgression:
        """Persists a new progression log record to database."""
        self.session.add(progression)
        return progression

    async def update(self, progression: StudentProgression) -> StudentProgression:
        """Updates an existing progression record."""
        self.session.add(progression)
        return progression

    async def delete(self, progression_id: uuid.UUID) -> bool:
        """Soft-deletes progression log record."""
        progression = await self.get_by_id(progression_id, include_deleted=True)
        if progression and not progression.is_deleted:
            progression.is_deleted = True
            progression.deleted_at = datetime.now(UTC)
            self.session.add(progression)
            return True
        return False

    async def restore(self, progression_id: uuid.UUID) -> bool:
        """Restores soft-deleted progression log record."""
        progression = await self.get_by_id(progression_id, include_deleted=True)
        if progression and progression.is_deleted:
            progression.is_deleted = False
            progression.deleted_at = None
            self.session.add(progression)
            return True
        return False

    async def get_by_id(
        self, progression_id: uuid.UUID, include_deleted: bool = False
    ) -> StudentProgression | None:
        """Retrieves progression record by UUID."""
        stmt = select(StudentProgression).where(StudentProgression.id == progression_id)
        if not include_deleted:
            stmt = stmt.where(StudentProgression.is_deleted == False)
        result = await self.session.execute(stmt)
        progression = result.scalar_one_or_none()
        return progression if isinstance(progression, StudentProgression) else None

    async def get_by_student(
        self, student_id: uuid.UUID, include_deleted: bool = False
    ) -> list[StudentProgression]:
        """Retrieves progression log list for student."""
        stmt = select(StudentProgression).where(
            StudentProgression.student_id == student_id
        )
        if not include_deleted:
            stmt = stmt.where(StudentProgression.is_deleted == False)
        stmt = stmt.order_by(StudentProgression.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_history(self, student_id: uuid.UUID) -> list[StudentProgression]:
        """Alias method to resolve student progression chronological logging sequence."""
        return await self.get_by_student(student_id)
