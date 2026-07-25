import uuid
from typing import Any

from sqlalchemy import func, or_, select

from app.modules.admission.models import Admission
from app.modules.guardian.models import Guardian
from app.modules.student.enums import StudentStatus
from app.modules.student.models import Student
from app.modules.student_assignment.enums import AssignmentStatus
from app.modules.student_assignment.models import StudentAcademicAssignment
from app.modules.student_documents.models import StudentDocument
from app.modules.student_medical.enums import AllergySeverity
from app.modules.student_medical.models import (
    Allergy,
    StudentMedicalRecord,
)
from app.modules.student_progression.enums import ProgressionType
from app.modules.student_progression.models import StudentProgression


class StudentDashboardRepository:
    """
    Repository class encapsulating database aggregation queries for Analytics and Dashboard insights.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_total_students_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Student.id)).where(
            Student.school_id == school_id, Student.is_deleted == False
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def get_students_count_by_status(
        self, school_id: uuid.UUID, status: StudentStatus
    ) -> int:
        stmt = select(func.count(Student.id)).where(
            Student.school_id == school_id,
            Student.status == status,
            Student.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def get_inactive_students_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(Student.id)).where(
            Student.school_id == school_id,
            or_(Student.is_active == False, Student.status == StudentStatus.DROPPED),
            Student.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def get_medical_alerts_count(self, school_id: uuid.UUID) -> int:
        # Count records with SEVERE allergies
        stmt = (
            select(func.count(func.distinct(StudentMedicalRecord.id)))
            .join(Allergy, Allergy.medical_record_id == StudentMedicalRecord.id)
            .where(
                StudentMedicalRecord.school_id == school_id,
                Allergy.severity == AllergySeverity.SEVERE,
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def get_pending_documents_count(self, school_id: uuid.UUID) -> int:
        stmt = select(func.count(StudentDocument.id)).where(
            StudentDocument.school_id == school_id,
            StudentDocument.is_verified == False,
            StudentDocument.is_deleted == False,
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def get_gender_breakdown(self, school_id: uuid.UUID) -> list[tuple[str, int]]:
        stmt = (
            select(Student.gender, func.count(Student.id))
            .where(Student.school_id == school_id, Student.is_deleted == False)
            .group_by(Student.gender)
        )
        res = await self.session.execute(stmt)
        return [
            (str(row[0].value) if row[0] else "Unknown", row[1]) for row in res.all()
        ]

    async def get_classwise_breakdown(
        self, school_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(
                StudentAcademicAssignment.class_id,
                func.count(StudentAcademicAssignment.id),
            )
            .where(
                StudentAcademicAssignment.school_id == school_id,
                StudentAcademicAssignment.status == AssignmentStatus.ACTIVE,
                StudentAcademicAssignment.is_deleted == False,
            )
            .group_by(StudentAcademicAssignment.class_id)
        )
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    async def get_sectionwise_breakdown(
        self, school_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(
                StudentAcademicAssignment.section_id,
                func.count(StudentAcademicAssignment.id),
            )
            .where(
                StudentAcademicAssignment.school_id == school_id,
                StudentAcademicAssignment.section_id.is_not(None),
                StudentAcademicAssignment.status == AssignmentStatus.ACTIVE,
                StudentAcademicAssignment.is_deleted == False,
            )
            .group_by(StudentAcademicAssignment.section_id)
        )
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    async def get_blood_group_breakdown(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        stmt = (
            select(Student.blood_group, func.count(Student.id))
            .where(Student.school_id == school_id, Student.is_deleted == False)
            .group_by(Student.blood_group)
        )
        res = await self.session.execute(stmt)
        return [(row[0] or "Unknown", row[1]) for row in res.all()]

    async def get_admissions_analytics(
        self, school_id: uuid.UUID
    ) -> list[tuple[str, int]]:
        stmt = (
            select(Admission.academic_year, func.count(Admission.id))
            .where(Admission.school_id == school_id, Admission.is_deleted == False)
            .group_by(Admission.academic_year)
        )
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    async def get_promotions_analytics(
        self, school_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(
                StudentProgression.to_academic_year_id,
                func.count(StudentProgression.id),
            )
            .where(
                StudentProgression.school_id == school_id,
                StudentProgression.progression_type == ProgressionType.PROMOTION,
                StudentProgression.is_deleted == False,
            )
            .group_by(StudentProgression.to_academic_year_id)
        )
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all() if row[0] is not None]

    async def get_graduations_analytics(
        self, school_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(
                StudentProgression.from_academic_year_id,
                func.count(StudentProgression.id),
            )
            .where(
                StudentProgression.school_id == school_id,
                StudentProgression.progression_type == ProgressionType.GRADUATION,
                StudentProgression.is_deleted == False,
            )
            .group_by(StudentProgression.from_academic_year_id)
        )
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all() if row[0] is not None]

    async def global_search(
        self, school_id: uuid.UUID, term: str
    ) -> tuple[list[Student], list[Guardian]]:
        pattern = f"%{term}%"

        # Search Students
        student_stmt = (
            select(Student)
            .where(
                Student.school_id == school_id,
                Student.is_deleted == False,
                or_(
                    Student.first_name.ilike(pattern),
                    Student.last_name.ilike(pattern),
                    Student.email.ilike(pattern),
                    Student.phone.ilike(pattern),
                    Student.admission_number.ilike(pattern),
                    Student.roll_number.ilike(pattern),
                ),
            )
            .limit(20)
        )
        student_res = await self.session.execute(student_stmt)
        students = list(student_res.scalars().all())

        # Search Guardians
        guardian_stmt = (
            select(Guardian)
            .where(
                Guardian.school_id == school_id,
                Guardian.is_deleted == False,
                or_(
                    Guardian.first_name.ilike(pattern),
                    Guardian.last_name.ilike(pattern),
                    Guardian.email.ilike(pattern),
                    Guardian.phone.ilike(pattern),
                    Guardian.aadhaar_number.ilike(pattern),
                ),
            )
            .limit(20)
        )
        guardian_res = await self.session.execute(guardian_stmt)
        guardians = list(guardian_res.scalars().all())

        return students, guardians
