import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.models import Student
from app.modules.student_assignment.enums import AssignmentStatus
from app.modules.student_assignment.exceptions import (
    AssignmentNotFoundException,
    DuplicateActiveAssignmentException,
    InvalidAssignmentDataException,
    RollNumberConflictException,
)
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_assignment.repository import (
    StudentAcademicAssignmentRepository,
)
from app.modules.student_assignment.schemas import (
    BulkAssignmentCreate,
    StudentAcademicAssignmentCreate,
    StudentAcademicAssignmentUpdate,
    TransferAssignmentRequest,
)
from app.modules.student_assignment.validators import validate_academic_metadata


class StudentAcademicAssignmentService:
    """
    Service class orchestrating business actions for Student Academic Assignments.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StudentAcademicAssignmentRepository(db)
        self.audit = AuditLogService(db)

    async def assign_student(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentAcademicAssignmentCreate,
    ) -> StudentAcademicAssignment:
        """Assigns a student to a class and section."""
        # 1. Verify student presence and school context
        student = await self.db.get(Student, data.student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        # 2. Enforce one active assignment constraint
        active_assignment = await self.repo.get_active_by_student(data.student_id)
        if active_assignment:
            raise DuplicateActiveAssignmentException()

        # 3. Validate master metadata configuration boundaries
        validate_academic_metadata(
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            section_id=data.section_id,
        )

        # 4. Check roll number uniqueness
        if data.roll_number:
            conflict = await self.repo.get_by_roll_number(
                school_id=school_id,
                academic_year_id=data.academic_year_id,
                class_id=data.class_id,
                section_id=data.section_id,
                roll_number=data.roll_number,
            )
            if conflict:
                raise RollNumberConflictException()

        assignment = StudentAcademicAssignment(
            school_id=school_id,
            student_id=data.student_id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            section_id=data.section_id,
            roll_number=data.roll_number,
            admission_type=data.admission_type,
            joined_on=data.joined_on,
            status=AssignmentStatus.ACTIVE,
            remarks=data.remarks,
        )

        await self.repo.create(assignment)
        await self.db.flush()

        # Log audit action
        await self.audit.log_action(
            module="student_assignment",
            action="assign",
            entity_name="StudentAcademicAssignment",
            entity_id=assignment.id,
            metadata_json={
                "student_id": str(data.student_id),
                "roll_number": data.roll_number,
            },
            user_id=user_id,
            school_id=school_id,
        )

        return assignment

    async def update_assignment(
        self,
        assignment_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentAcademicAssignmentUpdate,
    ) -> StudentAcademicAssignment:
        """Updates parameters of an existing academic assignment record."""
        assignment = await self.repo.get_by_id(assignment_id)
        if not assignment or assignment.school_id != school_id:
            raise AssignmentNotFoundException()

        # If updating roll number, check uniqueness
        if data.roll_number and data.roll_number != assignment.roll_number:
            conflict = await self.repo.get_by_roll_number(
                school_id=school_id,
                academic_year_id=assignment.academic_year_id,
                class_id=assignment.class_id,
                section_id=assignment.section_id,
                roll_number=data.roll_number,
            )
            if conflict:
                raise RollNumberConflictException()
            assignment.roll_number = data.roll_number

        if data.remarks is not None:
            assignment.remarks = data.remarks
        if data.status is not None:
            assignment.status = data.status
        if data.left_on is not None:
            assignment.left_on = data.left_on

        await self.repo.update(assignment)
        await self.db.flush()

        await self.audit.log_action(
            module="student_assignment",
            action="update",
            entity_name="StudentAcademicAssignment",
            entity_id=assignment.id,
            user_id=user_id,
            school_id=school_id,
        )

        return assignment

    async def delete_assignment(
        self,
        assignment_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft-deletes academic assignment record."""
        assignment = await self.repo.get_by_id(assignment_id)
        if not assignment or assignment.school_id != school_id:
            raise AssignmentNotFoundException()

        deleted = await self.repo.delete(assignment_id)
        if deleted:
            await self.db.flush()
            await self.audit.log_action(
                module="student_assignment",
                action="delete",
                entity_name="StudentAcademicAssignment",
                entity_id=assignment_id,
                user_id=user_id,
                school_id=school_id,
            )
        return deleted

    async def transfer_student(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TransferAssignmentRequest,
    ) -> StudentAcademicAssignment:
        """Executes class/section transfer workflow."""
        # 1. Enforce student presence
        student = await self.db.get(Student, data.student_id)
        if not student or student.school_id != school_id or student.is_deleted:
            raise StudentNotFoundException()

        # 2. Get active assignment
        active_assignment = await self.repo.get_active_by_student(data.student_id)
        if not active_assignment or active_assignment.school_id != school_id:
            raise AssignmentNotFoundException(
                "No active academic assignment found to transfer."
            )

        # If transfer targets identical class/section, raise exception
        if (
            active_assignment.class_id == data.new_class_id
            and active_assignment.section_id == data.new_section_id
            and active_assignment.academic_year_id == data.new_academic_year_id
        ):
            raise InvalidAssignmentDataException(
                "Student is already assigned to the target class and section."
            )

        # 3. Validate new academic metadata parameters
        validate_academic_metadata(
            academic_year_id=data.new_academic_year_id,
            class_id=data.new_class_id,
            section_id=data.new_section_id,
        )

        # 4. Mark current assignment as TRANSFERRED
        active_assignment.status = AssignmentStatus.TRANSFERRED
        active_assignment.left_on = data.transfer_date
        await self.repo.update(active_assignment)

        # 5. Determine next roll number dynamically in new section
        existing_in_section = (
            await self.repo.get_by_section(data.new_section_id)
            if data.new_section_id
            else []
        )
        active_rolls = [
            int(a.roll_number)
            for a in existing_in_section
            if a.roll_number
            and a.roll_number.isdigit()
            and a.status == AssignmentStatus.ACTIVE
        ]
        next_roll = str(max(active_rolls) + 1 if active_rolls else 1)

        # Create new ACTIVE assignment
        new_assignment = StudentAcademicAssignment(
            school_id=school_id,
            student_id=data.student_id,
            academic_year_id=data.new_academic_year_id,
            class_id=data.new_class_id,
            section_id=data.new_section_id,
            roll_number=next_roll,
            admission_type="transfer",
            joined_on=data.transfer_date,
            status=AssignmentStatus.ACTIVE,
            remarks=data.remarks,
        )

        await self.repo.create(new_assignment)
        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_assignment",
            action="transfer",
            entity_name="StudentAcademicAssignment",
            entity_id=new_assignment.id,
            metadata_json={"old_assignment_id": str(active_assignment.id)},
            user_id=user_id,
            school_id=school_id,
        )

        return new_assignment

    async def bulk_assign(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: BulkAssignmentCreate,
    ) -> list[StudentAcademicAssignment]:
        """Assigns multiple students to class/section simultaneously."""
        # Validate metadata first
        validate_academic_metadata(
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            section_id=data.section_id,
        )

        assignments: list[StudentAcademicAssignment] = []

        # Get initial starting roll value for auto-numbering
        existing_in_section = (
            await self.repo.get_by_section(data.section_id) if data.section_id else []
        )
        active_rolls = [
            int(a.roll_number)
            for a in existing_in_section
            if a.roll_number
            and a.roll_number.isdigit()
            and a.status == AssignmentStatus.ACTIVE
        ]
        next_roll_num = max(active_rolls) + 1 if active_rolls else 1

        for student_id in data.student_ids:
            student = await self.db.get(Student, student_id)
            if not student or student.school_id != school_id or student.is_deleted:
                raise StudentNotFoundException(f"Student {student_id} not found.")

            # Ensure no active duplicate assignments
            active_assignment = await self.repo.get_active_by_student(student_id)
            if active_assignment:
                raise DuplicateActiveAssignmentException(
                    f"Student {student_id} already has an active assignment."
                )

            assignment = StudentAcademicAssignment(
                school_id=school_id,
                student_id=student_id,
                academic_year_id=data.academic_year_id,
                class_id=data.class_id,
                section_id=data.section_id,
                roll_number=str(next_roll_num),
                admission_type="regular",
                joined_on=date.today(),
                status=AssignmentStatus.ACTIVE,
                remarks=data.remarks,
            )

            await self.repo.create(assignment)
            assignments.append(assignment)
            next_roll_num += 1

        await self.db.flush()

        # Audit
        await self.audit.log_action(
            module="student_assignment",
            action="bulk_assign",
            entity_name="StudentAcademicAssignment",
            entity_id=school_id,  # Context level
            metadata_json={"count": len(assignments)},
            user_id=user_id,
            school_id=school_id,
        )

        return assignments
