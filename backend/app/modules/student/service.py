import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.exceptions import BadRequestException
from app.models.school import School
from app.modules.student.enums import StudentStatus
from app.modules.student.exceptions import (
    DuplicateAdmissionNumberException,
    DuplicateEmailException,
    InvalidAdmissionDateException,
    InvalidAgeException,
    StudentNotFoundException,
)
from app.modules.student.models import Student
from app.modules.student.repository import StudentRepository
from app.modules.student.schemas import StudentCreate, StudentUpdate
from app.modules.student.validators import validate_student_dob


class StudentService:
    """
    Business service layer applying domain validation rules for Student records.
    """

    def __init__(self, repository: StudentRepository, session: AsyncSession) -> None:
        self.repo = repository
        self.session = session

    async def create_student(self, schema: StudentCreate) -> Student:
        """Applies business validations and persists a new student record."""
        # 1. Validate School tenant exists
        school_stmt = select(School).where(School.id == schema.school_id, School.is_deleted == False)
        school_res = await self.session.execute(school_stmt)
        if not school_res.scalar_one_or_none():
            raise StudentNotFoundException(f"School tenant with id {schema.school_id} not found.")

        # 2. Prevent duplicate admission number
        if await self.repo.exists_by_admission_number(schema.school_id, schema.admission_number):
            raise DuplicateAdmissionNumberException()

        # 3. Prevent duplicate email
        if schema.email and await self.repo.exists_by_email(schema.school_id, schema.email):
            raise DuplicateEmailException()

        # 4. Validate age limits (2 to 30 years old)
        try:
            validate_student_dob(schema.date_of_birth)
        except ValueError as exc:
            raise InvalidAgeException(str(exc))

        # 5. Validate joined and graduation dates
        today = date.today()
        if schema.joined_date > today:
            raise InvalidAdmissionDateException("Joined date cannot be in the future.")
        if schema.graduation_date and schema.graduation_date < schema.joined_date:
            raise InvalidAdmissionDateException("Graduation date must be after joined date.")

        # 6. Map to model and persist
        student = Student(
            school_id=schema.school_id,
            admission_number=schema.admission_number,
            roll_number=schema.roll_number,
            emis_number=schema.emis_number,
            first_name=schema.first_name,
            middle_name=schema.middle_name,
            last_name=schema.last_name,
            gender=schema.gender,
            date_of_birth=schema.date_of_birth,
            blood_group=schema.blood_group,
            email=schema.email,
            phone=schema.phone,
            aadhaar_number=schema.aadhaar_number,
            nationality=schema.nationality,
            religion=schema.religion,
            caste=schema.caste,
            community=schema.community,
            mother_tongue=schema.mother_tongue,
            photo_url=schema.photo_url,
            joined_date=schema.joined_date,
            graduation_date=schema.graduation_date,
            remarks=schema.remarks,
            status=StudentStatus.NEW,  # Force initial status to NEW on registration
        )
        result = await self.repo.create(student)
        await self.session.flush()  # Populate DB-generated fields (id, timestamps, defaults)
        return result

    async def update_student(self, student_id: uuid.UUID, schema: StudentUpdate) -> Student:
        """Applies mutation validations and updates student record details."""
        student = await self.repo.get_by_id(student_id)
        if not student:
            raise StudentNotFoundException()

        # 1. Prevent duplicate admission number if changed
        if schema.admission_number and schema.admission_number != student.admission_number:
            if await self.repo.exists_by_admission_number(student.school_id, schema.admission_number):
                raise DuplicateAdmissionNumberException()
            student.admission_number = schema.admission_number

        # 2. Prevent duplicate email if changed
        if schema.email and schema.email != student.email:
            if await self.repo.exists_by_email(student.school_id, schema.email):
                raise DuplicateEmailException()
            student.email = schema.email

        # 3. Validate age limits if DOB changed
        if schema.date_of_birth:
            try:
                validate_student_dob(schema.date_of_birth)
            except ValueError as exc:
                raise InvalidAgeException(str(exc))
            student.date_of_birth = schema.date_of_birth

        # 4. Validate admission overrides
        joined = schema.joined_date or student.joined_date
        grad = schema.graduation_date if schema.graduation_date is not None else student.graduation_date

        if schema.joined_date and schema.joined_date > date.today():
            raise InvalidAdmissionDateException("Joined date cannot be in the future.")

        if grad and grad < joined:
            raise InvalidAdmissionDateException("Graduation date must be after joined date.")

        if schema.joined_date:
            student.joined_date = schema.joined_date
        if schema.graduation_date is not None:
            student.graduation_date = schema.graduation_date

        # 5. Validate status transitions
        if schema.status and schema.status != student.status:
            # Transition back to NEW is prohibited once student has graduated/active/dropped
            if schema.status == StudentStatus.NEW and student.status != StudentStatus.NEW:
                raise BadRequestException("Cannot revert student status back to NEW.")
            student.status = schema.status

        # 6. Apply simple field mappings
        if schema.roll_number is not None:
            student.roll_number = schema.roll_number
        if schema.emis_number is not None:
            student.emis_number = schema.emis_number
        if schema.first_name is not None:
            student.first_name = schema.first_name
        if schema.middle_name is not None:
            student.middle_name = schema.middle_name
        if schema.last_name is not None:
            student.last_name = schema.last_name
        if schema.gender is not None:
            student.gender = schema.gender
        if schema.blood_group is not None:
            student.blood_group = schema.blood_group
        if schema.phone is not None:
            student.phone = schema.phone
        if schema.aadhaar_number is not None:
            student.aadhaar_number = schema.aadhaar_number
        if schema.nationality is not None:
            student.nationality = schema.nationality
        if schema.religion is not None:
            student.religion = schema.religion
        if schema.caste is not None:
            student.caste = schema.caste
        if schema.community is not None:
            student.community = schema.community
        if schema.mother_tongue is not None:
            student.mother_tongue = schema.mother_tongue
        if schema.photo_url is not None:
            student.photo_url = schema.photo_url
        if schema.is_active is not None:
            student.is_active = schema.is_active
        if schema.remarks is not None:
            student.remarks = schema.remarks

        result = await self.repo.update(student)
        await self.session.flush()  # Populate updated timestamps
        return result

    async def delete_student(self, student_id: uuid.UUID) -> bool:
        """Deletes a student record (soft-delete)."""
        student = await self.repo.get_by_id(student_id)
        if not student:
            raise StudentNotFoundException()
        return await self.repo.delete(student_id)

    async def restore_student(self, student_id: uuid.UUID) -> bool:
        """Restores a soft-deleted student record."""
        student = await self.repo.get_by_id(student_id, include_deleted=True)
        if not student:
            raise StudentNotFoundException()
        return await self.repo.restore(student_id)
