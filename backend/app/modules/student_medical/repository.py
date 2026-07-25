import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.modules.student_medical.models import (
    Allergy,
    StudentMedicalRecord,
    Vaccination,
)


class StudentMedicalRepository:
    """
    Repository class encapsulating database query actions for Student Medical profiles, Allergies, and Vaccinations.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(self, record: StudentMedicalRecord) -> StudentMedicalRecord:
        """Persists a new medical profile record to database."""
        self.session.add(record)
        return record

    async def update(self, record: StudentMedicalRecord) -> StudentMedicalRecord:
        """Updates an existing medical profile record."""
        self.session.add(record)
        return record

    async def delete(self, record_id: uuid.UUID) -> bool:
        """Performs soft-delete of student medical record."""
        record = await self.get_by_id(record_id, include_deleted=True)
        if record and not record.is_deleted:
            record.is_deleted = True
            record.deleted_at = datetime.now(UTC)
            self.session.add(record)
            return True
        return False

    async def restore(self, record_id: uuid.UUID) -> bool:
        """Restores a soft-deleted student medical record."""
        record = await self.get_by_id(record_id, include_deleted=True)
        if record and record.is_deleted:
            record.is_deleted = False
            record.deleted_at = None
            self.session.add(record)
            return True
        return False

    async def get_by_id(
        self, record_id: uuid.UUID, include_deleted: bool = False
    ) -> StudentMedicalRecord | None:
        """Retrieves a medical record by its UUID."""
        stmt = select(StudentMedicalRecord).where(StudentMedicalRecord.id == record_id)
        if not include_deleted:
            stmt = stmt.where(StudentMedicalRecord.is_deleted == False)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        return record if isinstance(record, StudentMedicalRecord) else None

    async def get_by_student(
        self, student_id: uuid.UUID, include_deleted: bool = False
    ) -> StudentMedicalRecord | None:
        """Retrieves active medical profile associated with a student."""
        stmt = select(StudentMedicalRecord).where(
            StudentMedicalRecord.student_id == student_id
        )
        if not include_deleted:
            stmt = stmt.where(StudentMedicalRecord.is_deleted == False)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        return record if isinstance(record, StudentMedicalRecord) else None

    async def add_allergy(self, allergy: Allergy) -> Allergy:
        """Persists a new allergy registry entry."""
        self.session.add(allergy)
        return allergy

    async def remove_allergy(self, allergy: Allergy) -> None:
        """Performs hard deletion of an allergy record."""
        await self.session.delete(allergy)

    async def add_vaccination(self, vaccination: Vaccination) -> Vaccination:
        """Persists a new vaccination record entry."""
        self.session.add(vaccination)
        return vaccination

    async def remove_vaccination(self, vaccination: Vaccination) -> None:
        """Performs hard deletion of a vaccination record."""
        await self.session.delete(vaccination)
