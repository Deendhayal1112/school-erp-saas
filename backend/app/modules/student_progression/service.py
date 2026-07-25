import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.modules.student.enums import StudentStatus
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.models import Student
from app.modules.student_assignment.enums import AssignmentStatus
from app.modules.student_assignment.exceptions import RollNumberConflictException
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_assignment.repository import (
    StudentAcademicAssignmentRepository,
)
from app.modules.student_progression.enums import ProgressionType
from app.modules.student_progression.exceptions import (
    InvalidProgressionDataException,
)
from app.modules.student_progression.models import StudentProgression
from app.modules.student_progression.repository import StudentProgressionRepository
from app.modules.student_progression.schemas import (
    AlumniConversionRequest,
    BulkPromotionRequest,
    StudentGraduationRequest,
    StudentPromotionRequest,
    StudentTransferRequest,
)
from app.modules.student_progression.validators import (
    validate_graduation_class,
    validate_promotion_sequence,
)


class StudentProgressionService:
    """
    Service class orchestrating business actions for Student Promotion, Transfer, Graduation and Alumni.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StudentProgressionRepository(db)
        self.assign_repo = StudentAcademicAssignmentRepository(db)
        self.audit = AuditLogService(db)

    async def promote_student(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentPromotionRequest,
    ) -> StudentProgression:
        """Promotes a single student to next class context."""
        # 1. Enforce student existence
        student = await self.db.get(Student, data.student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        # 2. Retrieve active assignment
        active_assignment = await self.assign_repo.get_active_by_student(
            data.student_id
        )
        if not active_assignment or active_assignment.school_id != school_id:
            raise InvalidProgressionDataException(
                "Student does not have an active academic assignment to promote."
            )

        # 3. Validate promotion sequence
        validate_promotion_sequence(
            from_year_id=active_assignment.academic_year_id,
            to_year_id=data.to_academic_year_id,
        )

        # 4. Check roll number uniqueness in target section
        if data.new_roll_number:
            conflict = await self.assign_repo.get_by_roll_number(
                school_id=school_id,
                academic_year_id=data.to_academic_year_id,
                class_id=data.to_class_id,
                section_id=data.to_section_id,
                roll_number=data.new_roll_number,
            )
            if conflict:
                raise RollNumberConflictException()

        # Close current assignment
        from_class_id = active_assignment.class_id
        from_section_id = active_assignment.section_id
        from_academic_year_id = active_assignment.academic_year_id
        old_roll = active_assignment.roll_number

        active_assignment.status = AssignmentStatus.PROMOTED
        active_assignment.left_on = date.today()
        await self.assign_repo.update(active_assignment)

        # Create new ACTIVE assignment
        new_assignment = StudentAcademicAssignment(
            school_id=school_id,
            student_id=data.student_id,
            academic_year_id=data.to_academic_year_id,
            class_id=data.to_class_id,
            section_id=data.to_section_id,
            roll_number=data.new_roll_number,
            admission_type="regular",
            joined_on=date.today(),
            status=AssignmentStatus.ACTIVE,
        )
        await self.assign_repo.create(new_assignment)

        # Update student status to active if they were new
        if student.status == StudentStatus.NEW:
            student.status = StudentStatus.ACTIVE
            self.db.add(student)

        # Create progression log
        progression = StudentProgression(
            school_id=school_id,
            student_id=data.student_id,
            from_academic_year_id=from_academic_year_id,
            to_academic_year_id=data.to_academic_year_id,
            from_class_id=from_class_id,
            to_class_id=data.to_class_id,
            from_section_id=from_section_id,
            to_section_id=data.to_section_id,
            old_roll_number=old_roll,
            new_roll_number=data.new_roll_number,
            progression_type=ProgressionType.PROMOTION,
            status="COMPLETED",
            approved_by=user_id,
            approved_at=datetime.utcnow(),
            remarks=data.remarks,
        )
        await self.repo.create(progression)
        await self.db.flush()

        # Audit Log trace
        await self.audit.log_action(
            module="student_progression",
            action="promote",
            entity_name="StudentProgression",
            entity_id=progression.id,
            metadata_json={"student_id": str(data.student_id)},
            user_id=user_id,
            school_id=school_id,
        )

        return progression

    async def bulk_promote(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: BulkPromotionRequest,
    ) -> list[StudentProgression]:
        """Bulk promotes list of students to target next year/class/section context."""
        progressions: list[StudentProgression] = []

        # Find max active roll number in target section to assign next sequential numbers
        existing_in_section = (
            await self.assign_repo.get_by_section(data.to_section_id)
            if data.to_section_id
            else []
        )
        active_rolls = [
            int(a.roll_number)
            for a in existing_in_section
            if a.roll_number
            and a.roll_number.isdigit()
            and a.status == AssignmentStatus.ACTIVE
        ]
        next_roll_val = max(active_rolls) + 1 if active_rolls else 1

        for student_id in data.student_ids:
            # We construct a single promote request and run the business action
            promo_req = StudentPromotionRequest(
                student_id=student_id,
                to_academic_year_id=data.to_academic_year_id,
                to_class_id=data.to_class_id,
                to_section_id=data.to_section_id,
                new_roll_number=str(next_roll_val),
                remarks=data.remarks,
            )
            progression = await self.promote_student(school_id, user_id, promo_req)
            progressions.append(progression)
            next_roll_val += 1

        # Audit
        await self.audit.log_action(
            module="student_progression",
            action="bulk_promote",
            entity_name="StudentProgression",
            entity_id=school_id,
            metadata_json={"count": len(progressions)},
            user_id=user_id,
            school_id=school_id,
        )

        return progressions

    async def transfer_student(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentTransferRequest,
    ) -> StudentProgression:
        """Transfers a student class/section context logging progression history."""
        student = await self.db.get(Student, data.student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        active_assignment = await self.assign_repo.get_active_by_student(
            data.student_id
        )
        if not active_assignment or active_assignment.school_id != school_id:
            raise InvalidProgressionDataException(
                "Student does not have an active assignment to transfer."
            )

        # Close current assignment
        from_class_id = active_assignment.class_id
        from_section_id = active_assignment.section_id
        from_academic_year_id = active_assignment.academic_year_id
        old_roll = active_assignment.roll_number

        active_assignment.status = AssignmentStatus.TRANSFERRED
        active_assignment.left_on = date.today()
        await self.assign_repo.update(active_assignment)

        # Get next sequential roll number
        existing_in_section = (
            await self.assign_repo.get_by_section(data.to_section_id)
            if data.to_section_id
            else []
        )
        active_rolls = [
            int(a.roll_number)
            for a in existing_in_section
            if a.roll_number
            and a.roll_number.isdigit()
            and a.status == AssignmentStatus.ACTIVE
        ]
        new_roll = str(max(active_rolls) + 1 if active_rolls else 1)

        # Create new ACTIVE assignment
        new_assignment = StudentAcademicAssignment(
            school_id=school_id,
            student_id=data.student_id,
            academic_year_id=data.to_academic_year_id,
            class_id=data.to_class_id,
            section_id=data.to_section_id,
            roll_number=new_roll,
            admission_type="transfer",
            joined_on=date.today(),
            status=AssignmentStatus.ACTIVE,
        )
        await self.assign_repo.create(new_assignment)

        # Create progression log
        progression = StudentProgression(
            school_id=school_id,
            student_id=data.student_id,
            from_academic_year_id=from_academic_year_id,
            to_academic_year_id=data.to_academic_year_id,
            from_class_id=from_class_id,
            to_class_id=data.to_class_id,
            from_section_id=from_section_id,
            to_section_id=data.to_section_id,
            old_roll_number=old_roll,
            new_roll_number=new_roll,
            progression_type=ProgressionType.TRANSFER,
            status="COMPLETED",
            approved_by=user_id,
            approved_at=datetime.utcnow(),
            remarks=data.remarks,
        )
        await self.repo.create(progression)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_progression",
            action="transfer",
            entity_name="StudentProgression",
            entity_id=progression.id,
            user_id=user_id,
            school_id=school_id,
        )

        return progression

    async def graduate_student(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentGraduationRequest,
    ) -> StudentProgression:
        """Graduates a student, closing current academic assignment and updating enrollment status."""
        student = await self.db.get(Student, data.student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        active_assignment = await self.assign_repo.get_active_by_student(
            data.student_id
        )
        if not active_assignment or active_assignment.school_id != school_id:
            raise InvalidProgressionDataException(
                "Student does not have an active assignment to graduate."
            )

        # Enforce final class constraints
        validate_graduation_class(active_assignment.class_id)

        # Close current assignment
        from_class_id = active_assignment.class_id
        from_section_id = active_assignment.section_id
        from_academic_year_id = active_assignment.academic_year_id
        old_roll = active_assignment.roll_number

        active_assignment.status = AssignmentStatus.GRADUATED
        active_assignment.left_on = date.today()
        await self.assign_repo.update(active_assignment)

        # Update student status
        student.status = StudentStatus.GRADUATED
        self.db.add(student)

        # Create progression log
        progression = StudentProgression(
            school_id=school_id,
            student_id=data.student_id,
            from_academic_year_id=from_academic_year_id,
            to_academic_year_id=None,
            from_class_id=from_class_id,
            to_class_id=None,
            from_section_id=from_section_id,
            to_section_id=None,
            old_roll_number=old_roll,
            new_roll_number=None,
            progression_type=ProgressionType.GRADUATION,
            status="COMPLETED",
            approved_by=user_id,
            approved_at=datetime.utcnow(),
            remarks=data.remarks,
        )
        await self.repo.create(progression)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_progression",
            action="graduate",
            entity_name="StudentProgression",
            entity_id=progression.id,
            user_id=user_id,
            school_id=school_id,
        )

        return progression

    async def convert_to_alumni(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AlumniConversionRequest,
    ) -> StudentProgression:
        """Converts a student to alumni status."""
        student = await self.db.get(Student, data.student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        active_assignment = await self.assign_repo.get_active_by_student(
            data.student_id
        )
        if not active_assignment or active_assignment.school_id != school_id:
            raise InvalidProgressionDataException(
                "Student does not have an active assignment."
            )

        # Close current assignment
        from_class_id = active_assignment.class_id
        from_section_id = active_assignment.section_id
        from_academic_year_id = active_assignment.academic_year_id
        old_roll = active_assignment.roll_number

        active_assignment.status = AssignmentStatus.LEFT
        active_assignment.left_on = date.today()
        await self.assign_repo.update(active_assignment)

        # Update student status
        student.status = StudentStatus.ALUMNI
        self.db.add(student)

        # Create progression log
        progression = StudentProgression(
            school_id=school_id,
            student_id=data.student_id,
            from_academic_year_id=from_academic_year_id,
            to_academic_year_id=None,
            from_class_id=from_class_id,
            to_class_id=None,
            from_section_id=from_section_id,
            to_section_id=None,
            old_roll_number=old_roll,
            new_roll_number=None,
            progression_type=ProgressionType.ALUMNI,
            status="COMPLETED",
            approved_by=user_id,
            approved_at=datetime.utcnow(),
            remarks=data.remarks,
        )
        await self.repo.create(progression)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_progression",
            action="convert_alumni",
            entity_name="StudentProgression",
            entity_id=progression.id,
            user_id=user_id,
            school_id=school_id,
        )

        return progression

    async def get_progression_history(
        self,
        student_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> list[StudentProgression]:
        """Resolves historical list of progressions for a student profile."""
        student = await self.db.get(Student, student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        return await self.repo.get_history(student_id)
