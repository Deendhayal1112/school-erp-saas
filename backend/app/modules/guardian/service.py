import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guardian.exceptions import (
    DuplicateGuardianAadhaarException,
    DuplicateGuardianEmailException,
    DuplicateGuardianPhoneException,
    GuardianNotFoundException,
)
from app.modules.guardian.models import Guardian, StudentGuardian
from app.modules.guardian.repository import GuardianRepository
from app.modules.guardian.schemas import (
    GuardianCreate,
    GuardianUpdate,
    StudentGuardianMappingCreate,
    StudentGuardianMappingUpdate,
)
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.repository import StudentRepository


class GuardianService:
    """
    Guardian Service layer orchestrating domain operations, mapping
    associations, tenant validations, and transactional commits.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = GuardianRepository(session)
        self.student_repo = StudentRepository(session)

    async def create_guardian(self, schema: GuardianCreate) -> Guardian:
        """Enforces duplicate constraints and creates a new guardian."""
        # 1. Phone duplication validation
        if await self.repo.exists_by_phone(schema.school_id, schema.phone):
            raise DuplicateGuardianPhoneException()

        # 2. Email duplication validation
        if schema.email and await self.repo.exists_by_email(
            schema.school_id, schema.email
        ):
            raise DuplicateGuardianEmailException()

        # 3. Aadhaar duplication validation
        if schema.aadhaar_number and await self.repo.exists_by_aadhaar(
            schema.school_id, schema.aadhaar_number
        ):
            raise DuplicateGuardianAadhaarException()

        guardian = Guardian(
            school_id=schema.school_id,
            first_name=schema.first_name,
            middle_name=schema.middle_name,
            last_name=schema.last_name,
            relationship=schema.relationship,
            occupation=schema.occupation,
            qualification=schema.qualification,
            annual_income=schema.annual_income,
            email=schema.email,
            phone=schema.phone,
            alternate_phone=schema.alternate_phone,
            aadhaar_number=schema.aadhaar_number,
            address=schema.address,
            city=schema.city,
            state=schema.state,
            country=schema.country,
            postal_code=schema.postal_code,
            is_primary_guardian=schema.is_primary_guardian,
            is_emergency_contact=schema.is_emergency_contact,
            remarks=schema.remarks,
        )
        await self.repo.create(guardian)
        await self.session.flush()
        return guardian

    async def update_guardian(
        self, guardian_id: uuid.UUID, schema: GuardianUpdate, school_id: uuid.UUID
    ) -> Guardian:
        """Applies validation mutations and updates guardian details."""
        guardian = await self.repo.get_by_id(guardian_id)
        if not guardian or guardian.school_id != school_id:
            raise GuardianNotFoundException()

        update_dict = schema.model_dump(exclude_unset=True)

        # Validate unique updates
        if update_dict.get("phone"):
            if await self.repo.exists_by_phone(
                school_id, update_dict["phone"], exclude_id=guardian_id
            ):
                raise DuplicateGuardianPhoneException()

        if update_dict.get("email"):
            if await self.repo.exists_by_email(
                school_id, update_dict["email"], exclude_id=guardian_id
            ):
                raise DuplicateGuardianEmailException()

        if update_dict.get("aadhaar_number"):
            if await self.repo.exists_by_aadhaar(
                school_id, update_dict["aadhaar_number"], exclude_id=guardian_id
            ):
                raise DuplicateGuardianAadhaarException()

        updated = await self.repo.update(guardian_id, update_dict)
        if not updated:
            raise GuardianNotFoundException()
        await self.session.flush()
        return updated

    async def delete_guardian(
        self, guardian_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
        """Soft-deletes a guardian matching tenant boundary rules."""
        guardian = await self.repo.get_by_id(guardian_id)
        if not guardian or guardian.school_id != school_id:
            raise GuardianNotFoundException()
        await self.repo.delete(guardian_id)
        await self.session.flush()

    async def restore_guardian(
        self, guardian_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
        """Restores a soft-deleted guardian."""
        guardian = await self.repo.get_by_id(guardian_id, include_deleted=True)
        if not guardian or guardian.school_id != school_id:
            raise GuardianNotFoundException()
        await self.repo.restore(guardian_id)
        await self.session.flush()

    # ==========================================
    # Student-Guardian Mapping Service Methods
    # ==========================================

    async def map_student_to_guardian(
        self,
        student_id: uuid.UUID,
        schema: StudentGuardianMappingCreate,
        school_id: uuid.UUID,
    ) -> StudentGuardian:
        """Maps a student to a guardian, enforcing primary flag singularity rules."""
        # 1. Enforce student existence & tenant
        student = await self.student_repo.get_by_id(student_id)
        if not student or student.school_id != school_id:
            raise StudentNotFoundException()

        # 2. Enforce guardian existence & tenant
        guardian = await self.repo.get_by_id(schema.guardian_id)
        if not guardian or guardian.school_id != school_id:
            raise GuardianNotFoundException()

        # 3. Check for existing mapping
        existing = await self.repo.get_mapping(student_id, schema.guardian_id)
        if existing:
            # Update mapping instead of creating duplicate
            existing.relationship_type = schema.relationship_type
            if schema.is_primary_guardian:
                await self.repo.unset_primary_guardians(student_id)
                existing.is_primary_guardian = True
            else:
                existing.is_primary_guardian = schema.is_primary_guardian
            existing.is_emergency_contact = schema.is_emergency_contact
            existing.is_pickup_authorized = schema.is_pickup_authorized
            self.session.add(existing)
            await self.session.flush()
            return existing

        # 4. Handle primary guardian isolation
        if schema.is_primary_guardian:
            await self.repo.unset_primary_guardians(student_id)

        mapping = StudentGuardian(
            student_id=student_id,
            guardian_id=schema.guardian_id,
            relationship_type=schema.relationship_type,
            is_primary_guardian=schema.is_primary_guardian,
            is_emergency_contact=schema.is_emergency_contact,
            is_pickup_authorized=schema.is_pickup_authorized,
        )
        await self.repo.create_mapping(mapping)
        await self.session.flush()
        return mapping

    async def update_mapping(
        self,
        student_id: uuid.UUID,
        guardian_id: uuid.UUID,
        schema: StudentGuardianMappingUpdate,
        school_id: uuid.UUID,
    ) -> StudentGuardian:
        """Modifies parameters on a student-guardian mapping relationship."""
        # 1. Enforce student existence & tenant
        student = await self.student_repo.get_by_id(student_id)
        if not student or student.school_id != school_id:
            raise StudentNotFoundException()

        # 2. Enforce guardian existence & tenant
        guardian = await self.repo.get_by_id(guardian_id)
        if not guardian or guardian.school_id != school_id:
            raise GuardianNotFoundException()

        # 3. Enforce mapping existence
        mapping = await self.repo.get_mapping(student_id, guardian_id)
        if not mapping:
            raise GuardianNotFoundException("Mapping relationship not found.")

        # Update mapping fields
        update_dict = schema.model_dump(exclude_unset=True)

        if update_dict.get("relationship_type"):
            mapping.relationship_type = update_dict["relationship_type"]

        if "is_primary_guardian" in update_dict:
            is_primary = update_dict["is_primary_guardian"]
            if is_primary:
                await self.repo.unset_primary_guardians(student_id)
            mapping.is_primary_guardian = is_primary

        if "is_emergency_contact" in update_dict:
            mapping.is_emergency_contact = update_dict["is_emergency_contact"]

        if "is_pickup_authorized" in update_dict:
            mapping.is_pickup_authorized = update_dict["is_pickup_authorized"]

        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def unmap_student_guardian(
        self, student_id: uuid.UUID, guardian_id: uuid.UUID, school_id: uuid.UUID
    ) -> None:
        """Removes the mapping relationship between a student and a guardian."""
        # 1. Enforce student existence & tenant
        student = await self.student_repo.get_by_id(student_id)
        if not student or student.school_id != school_id:
            raise StudentNotFoundException()

        # 2. Enforce guardian existence & tenant
        guardian = await self.repo.get_by_id(guardian_id)
        if not guardian or guardian.school_id != school_id:
            raise GuardianNotFoundException()

        deleted = await self.repo.delete_mapping(student_id, guardian_id)
        if not deleted:
            raise GuardianNotFoundException("Mapping relationship not found.")
        await self.session.flush()

    async def get_mapped_guardians(
        self, student_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[StudentGuardian]:
        """Retrieves list of active mapped guardians for a student."""
        student = await self.student_repo.get_by_id(student_id)
        if not student or student.school_id != school_id:
            raise StudentNotFoundException()
        return await self.repo.get_mappings_by_student_id(student_id)
