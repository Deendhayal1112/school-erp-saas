import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.exceptions.exceptions import BadRequestException
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.models import Student
from app.modules.student_medical.exceptions import (
    AllergyNotFoundException,
    MedicalRecordAlreadyExistsException,
    MedicalRecordNotFoundException,
    VaccinationNotFoundException,
)
from app.modules.student_medical.models import (
    Allergy,
    StudentMedicalRecord,
    Vaccination,
)
from app.modules.student_medical.repository import StudentMedicalRepository
from app.modules.student_medical.schemas import (
    AllergyCreate,
    StudentMedicalRecordCreate,
    StudentMedicalRecordUpdate,
    VaccinationCreate,
)
from app.modules.student_medical.validators import (
    validate_dates,
    validate_phone,
    validate_vitals,
)


class StudentMedicalService:
    """
    Service class managing business logic workflows for Student Medical profiles, Allergies, and Vaccinations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StudentMedicalRepository(db)
        self.audit = AuditLogService(db)

    def _calculate_bmi(
        self, height_cm: float | None, weight_kg: float | None
    ) -> float | None:
        """Calculates BMI index using metric unit parameters."""
        if not height_cm or not weight_kg:
            return None
        height_m = height_cm / 100.0
        return round(weight_kg / (height_m * height_m), 2)

    async def create_medical_record(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentMedicalRecordCreate,
    ) -> StudentMedicalRecord:
        """Creates a new student medical record."""
        # 1. Enforce student presence & school bounds
        student = await self.db.get(Student, student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        # 2. Check duplicate records
        existing = await self.repo.get_by_student(student_id)
        if existing:
            raise MedicalRecordAlreadyExistsException()

        # 3. Validations
        validate_vitals(data.height_cm, data.weight_kg)
        validate_phone(data.doctor_phone)
        validate_dates(data.last_medical_checkup, data.next_medical_checkup)

        # 4. BMI calculation
        bmi = self._calculate_bmi(data.height_cm, data.weight_kg)

        record = StudentMedicalRecord(
            school_id=school_id,
            student_id=student_id,
            blood_group=data.blood_group,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            bmi=bmi,
            vision_left=data.vision_left,
            vision_right=data.vision_right,
            hearing_status=data.hearing_status,
            medical_conditions=data.medical_conditions,
            chronic_diseases=data.chronic_diseases,
            current_medications=data.current_medications,
            doctor_name=data.doctor_name,
            hospital_name=data.hospital_name,
            doctor_phone=data.doctor_phone,
            insurance_provider=data.insurance_provider,
            insurance_policy_number=data.insurance_policy_number,
            medical_notes=data.medical_notes,
            is_fit_for_school=data.is_fit_for_school,
            last_medical_checkup=data.last_medical_checkup,
            next_medical_checkup=data.next_medical_checkup,
        )

        await self.repo.create(record)
        await self.db.flush()

        # Update student blood group if provided
        if data.blood_group:
            student.blood_group = data.blood_group.value
            self.db.add(student)

        # 5. Audit Log trace
        await self.audit.log_action(
            module="student_medical",
            action="create",
            entity_name="StudentMedicalRecord",
            entity_id=record.id,
            metadata_json={
                "blood_group": data.blood_group.value if data.blood_group else None
            },
            user_id=user_id,
            school_id=school_id,
        )

        return record

    async def update_medical_record(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentMedicalRecordUpdate,
    ) -> StudentMedicalRecord:
        """Updates fields of student medical record."""
        # Enforce student presence
        student = await self.db.get(Student, student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        record = await self.repo.get_by_student(student_id)
        if not record:
            raise MedicalRecordNotFoundException()

        # Validations
        validate_vitals(data.height_cm, data.weight_kg)
        validate_phone(data.doctor_phone)
        validate_dates(data.last_medical_checkup, data.next_medical_checkup)

        # Update columns
        record.blood_group = data.blood_group
        record.height_cm = data.height_cm
        record.weight_kg = data.weight_kg
        record.bmi = self._calculate_bmi(data.height_cm, data.weight_kg)

        record.vision_left = data.vision_left
        record.vision_right = data.vision_right
        record.hearing_status = data.hearing_status

        record.medical_conditions = data.medical_conditions
        record.chronic_diseases = data.chronic_diseases
        record.current_medications = data.current_medications

        record.doctor_name = data.doctor_name
        record.hospital_name = data.hospital_name
        record.doctor_phone = data.doctor_phone

        record.insurance_provider = data.insurance_provider
        record.insurance_policy_number = data.insurance_policy_number
        record.medical_notes = data.medical_notes
        record.is_fit_for_school = data.is_fit_for_school

        record.last_medical_checkup = data.last_medical_checkup
        record.next_medical_checkup = data.next_medical_checkup

        await self.repo.update(record)
        await self.db.flush()

        # Update student blood group if provided
        if data.blood_group:
            student.blood_group = data.blood_group.value
            self.db.add(student)

        # Audit
        await self.audit.log_action(
            module="student_medical",
            action="update",
            entity_name="StudentMedicalRecord",
            entity_id=record.id,
            user_id=user_id,
            school_id=school_id,
        )

        return record

    async def get_medical_record(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> StudentMedicalRecord:
        """Retrieves active medical record associated with a student."""
        # Enforce student presence & school bounds
        student = await self.db.get(Student, student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        record = await self.repo.get_by_student(student_id)
        if not record:
            raise MedicalRecordNotFoundException()

        return record

    async def delete_medical_record(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft deletes medical record of student."""
        student = await self.db.get(Student, student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        record = await self.repo.get_by_student(student_id)
        if not record:
            raise MedicalRecordNotFoundException()

        deleted = await self.repo.delete(record.id)
        if deleted:
            await self.db.flush()
            # Audit
            await self.audit.log_action(
                module="student_medical",
                action="delete",
                entity_name="StudentMedicalRecord",
                entity_id=record.id,
                user_id=user_id,
                school_id=school_id,
            )
        return deleted

    async def add_allergy(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AllergyCreate,
    ) -> Allergy:
        """Registers a new allergy entry mapping to student medical profile."""
        record = await self.get_medical_record(student_id, school_id)

        allergy = Allergy(
            medical_record_id=record.id,
            allergy_name=data.allergy_name,
            severity=data.severity,
            reaction=data.reaction,
            treatment=data.treatment,
            remarks=data.remarks,
        )

        await self.repo.add_allergy(allergy)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_medical",
            action="add_allergy",
            entity_name="Allergy",
            entity_id=allergy.id,
            metadata_json={"allergy_name": data.allergy_name},
            user_id=user_id,
            school_id=school_id,
        )

        return allergy

    async def remove_allergy(
        self,
        student_id: uuid.UUID,
        allergy_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Removes/Hard deletes an allergy record."""
        record = await self.get_medical_record(student_id, school_id)

        # Retrieve allergy and check relationship bounds
        allergy = await self.db.get(Allergy, allergy_id)
        if not allergy or allergy.medical_record_id != record.id or allergy.is_deleted:
            raise AllergyNotFoundException()

        await self.repo.remove_allergy(allergy)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_medical",
            action="remove_allergy",
            entity_name="Allergy",
            entity_id=allergy_id,
            user_id=user_id,
            school_id=school_id,
        )

    async def add_vaccination(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: VaccinationCreate,
    ) -> Vaccination:
        """Registers a new vaccination entry mapping to student medical profile."""
        record = await self.get_medical_record(student_id, school_id)

        # Validate date chronological dependencies
        if (
            data.next_due_date is not None
            and data.next_due_date < data.vaccination_date
        ):
            raise BadRequestException(
                "Next due date cannot be before vaccination date."
            )

        vaccination = Vaccination(
            medical_record_id=record.id,
            vaccine_name=data.vaccine_name,
            dose_number=data.dose_number,
            vaccination_date=data.vaccination_date,
            next_due_date=data.next_due_date,
            hospital=data.hospital,
            doctor=data.doctor,
            remarks=data.remarks,
        )

        await self.repo.add_vaccination(vaccination)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_medical",
            action="add_vaccination",
            entity_name="Vaccination",
            entity_id=vaccination.id,
            metadata_json={
                "vaccine_name": data.vaccine_name,
                "dose_number": data.dose_number,
            },
            user_id=user_id,
            school_id=school_id,
        )

        return vaccination

    async def remove_vaccination(
        self,
        student_id: uuid.UUID,
        vaccination_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Removes/Hard deletes a vaccination record."""
        record = await self.get_medical_record(student_id, school_id)

        vaccination = await self.db.get(Vaccination, vaccination_id)
        if (
            not vaccination
            or vaccination.medical_record_id != record.id
            or vaccination.is_deleted
        ):
            raise VaccinationNotFoundException()

        await self.repo.remove_vaccination(vaccination)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_medical",
            action="remove_vaccination",
            entity_name="Vaccination",
            entity_id=vaccination_id,
            user_id=user_id,
            school_id=school_id,
        )
