import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.exceptions import BadRequestException
from app.modules.admission.enums import AdmissionStatus
from app.modules.admission.exceptions import (
    AdmissionNotFoundException,
    DuplicateAdmissionApplicationException,
    InvalidAdmissionTransitionException,
    StudentGuardianRequiredException,
)
from app.modules.admission.models import Admission, AdmissionTimeline
from app.modules.admission.repository import AdmissionRepository
from app.modules.admission.schemas import AdmissionCreate, AdmissionUpdate
from app.modules.guardian.repository import GuardianRepository
from app.modules.student.enums import StudentStatus
from app.modules.student.exceptions import StudentNotFoundException
from app.modules.student.repository import StudentRepository


class AdmissionService:
    """
    Admission Service orchestrating the application workflow, state machine transitions,
    document verification checks, and final student enrollment number updates.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AdmissionRepository(session)
        self.student_repo = StudentRepository(session)
        self.guardian_repo = GuardianRepository(session)

    async def create_application(
        self, schema: AdmissionCreate, school_id: uuid.UUID
    ) -> Admission:
        """Creates a new student admission application in DRAFT state."""
        # 1. Enforce student existence and tenant boundary
        student = await self.student_repo.get_by_id(schema.student_id)
        if not student or student.school_id != school_id:
            raise StudentNotFoundException(
                "Target student profile not found in this school."
            )

        # 2. Check duplicate application
        if await self.repo.exists_by_student_id(school_id, schema.student_id):
            raise DuplicateAdmissionApplicationException()

        # 3. Generate unique application number
        app_suffix = uuid.uuid4().hex[:8].upper()
        application_number = f"APP-{app_suffix}"

        admission = Admission(
            school_id=school_id,
            application_number=application_number,
            student_id=schema.student_id,
            academic_year=schema.academic_year,
            class_id=schema.class_id,
            section_id=schema.section_id,
            admission_date=schema.admission_date,
            application_date=schema.application_date,
            status=AdmissionStatus.DRAFT,
            remarks=schema.remarks,
            documents_verified=schema.documents_verified,
            fees_paid=schema.fees_paid,
        )

        await self.repo.create_admission(admission)
        await self.session.flush()

        # Create initial timeline entry
        timeline = AdmissionTimeline(
            admission_id=admission.id,
            from_status=AdmissionStatus.DRAFT,
            to_status=AdmissionStatus.DRAFT,
            remarks="Application draft created.",
        )
        await self.repo.create_timeline(timeline)
        await self.session.flush()

        return admission

    async def update_application(
        self, admission_id: uuid.UUID, schema: AdmissionUpdate, school_id: uuid.UUID
    ) -> Admission:
        """Updates fields on a DRAFT or UNDER_REVIEW admission application."""
        admission = await self.repo.get_admission_by_id(admission_id)
        if not admission or admission.school_id != school_id:
            raise AdmissionNotFoundException()

        # If already enrolled or approved/rejected, block general edits unless allowed
        if admission.status in (AdmissionStatus.ENROLLED, AdmissionStatus.REJECTED):
            raise BadRequestException(
                f"Cannot update application in {admission.status} state."
            )

        update_dict = schema.model_dump(exclude_unset=True)
        updated = await self.repo.update_admission(admission_id, update_dict)
        if not updated:
            raise AdmissionNotFoundException()
        await self.session.flush()
        return updated

    async def submit_application(
        self,
        admission_id: uuid.UUID,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        remarks: str | None = None,
    ) -> Admission:
        """Transitions application state from DRAFT to SUBMITTED."""
        admission = await self.repo.get_admission_by_id(admission_id)
        if not admission or admission.school_id != school_id:
            raise AdmissionNotFoundException()

        if admission.status != AdmissionStatus.DRAFT:
            raise InvalidAdmissionTransitionException(
                "Only draft applications can be submitted."
            )

        # ENFORCE Guardian Required validation
        guardians = await self.guardian_repo.get_mappings_by_student_id(
            admission.student_id
        )
        if not guardians:
            raise StudentGuardianRequiredException()

        # Record timeline audit entry
        timeline = AdmissionTimeline(
            admission_id=admission.id,
            from_status=admission.status,
            to_status=AdmissionStatus.SUBMITTED,
            action_by=user_id,
            remarks=remarks or "Application submitted for review.",
        )
        await self.repo.create_timeline(timeline)

        admission.status = AdmissionStatus.SUBMITTED
        self.session.add(admission)
        await self.session.flush()
        return admission

    async def start_review(
        self,
        admission_id: uuid.UUID,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        remarks: str | None = None,
    ) -> Admission:
        """Transitions application state from SUBMITTED to UNDER_REVIEW."""
        admission = await self.repo.get_admission_by_id(admission_id)
        if not admission or admission.school_id != school_id:
            raise AdmissionNotFoundException()

        if admission.status != AdmissionStatus.SUBMITTED:
            raise InvalidAdmissionTransitionException(
                "Only submitted applications can be placed under review."
            )

        timeline = AdmissionTimeline(
            admission_id=admission.id,
            from_status=admission.status,
            to_status=AdmissionStatus.UNDER_REVIEW,
            action_by=user_id,
            remarks=remarks or "Application review started.",
        )
        await self.repo.create_timeline(timeline)

        admission.status = AdmissionStatus.UNDER_REVIEW
        self.session.add(admission)
        await self.session.flush()
        return admission

    async def approve_application(
        self,
        admission_id: uuid.UUID,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        remarks: str | None = None,
    ) -> Admission:
        """Approves a reviewable application, transition to APPROVED state."""
        admission = await self.repo.get_admission_by_id(admission_id)
        if not admission or admission.school_id != school_id:
            raise AdmissionNotFoundException()

        if admission.status not in (
            AdmissionStatus.SUBMITTED,
            AdmissionStatus.UNDER_REVIEW,
        ):
            raise InvalidAdmissionTransitionException(
                "Only submitted or under-review applications can be approved."
            )

        # Document verification validation check
        if not admission.documents_verified:
            raise BadRequestException(
                "Documents must be verified prior to application approval."
            )

        timeline = AdmissionTimeline(
            admission_id=admission.id,
            from_status=admission.status,
            to_status=AdmissionStatus.APPROVED,
            action_by=user_id,
            remarks=remarks or "Application approved.",
        )
        await self.repo.create_timeline(timeline)

        admission.status = AdmissionStatus.APPROVED
        admission.approved_by = user_id
        admission.approved_at = datetime.utcnow()
        self.session.add(admission)
        await self.session.flush()
        return admission

    async def reject_application(
        self,
        admission_id: uuid.UUID,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        rejection_reason: str,
        remarks: str | None = None,
    ) -> Admission:
        """Rejects the admission application."""
        admission = await self.repo.get_admission_by_id(admission_id)
        if not admission or admission.school_id != school_id:
            raise AdmissionNotFoundException()

        if admission.status in (AdmissionStatus.ENROLLED, AdmissionStatus.REJECTED):
            raise InvalidAdmissionTransitionException(
                f"Cannot reject application in {admission.status} state."
            )

        timeline = AdmissionTimeline(
            admission_id=admission.id,
            from_status=admission.status,
            to_status=AdmissionStatus.REJECTED,
            action_by=user_id,
            remarks=remarks or f"Application rejected. Reason: {rejection_reason}",
        )
        await self.repo.create_timeline(timeline)

        admission.status = AdmissionStatus.REJECTED
        admission.rejected_by = user_id
        admission.rejected_at = datetime.utcnow()
        admission.rejection_reason = rejection_reason
        self.session.add(admission)
        await self.session.flush()
        return admission

    async def enroll_student(
        self,
        admission_id: uuid.UUID,
        user_id: uuid.UUID,
        school_id: uuid.UUID,
        remarks: str | None = None,
    ) -> Admission:
        """
        Officially enrolls the student. Generates a unique Admission Number,
        updates the student profile to ACTIVE, and marks the workflow ENROLLED.
        """
        admission = await self.repo.get_admission_by_id(admission_id)
        if not admission or admission.school_id != school_id:
            raise AdmissionNotFoundException()

        if admission.status != AdmissionStatus.APPROVED:
            raise InvalidAdmissionTransitionException(
                "Only approved applications can be enrolled."
            )

        # Validate fees paid
        if not admission.fees_paid:
            raise BadRequestException(
                "Admission fees must be paid prior to student enrollment."
            )

        # Generate unique sequential admission number
        current_year = datetime.utcnow().year
        official_admission_number = await self.repo.get_next_sequence_value(
            school_id, current_year
        )

        # Update linked student record status and admission number
        student = await self.student_repo.get_by_id(admission.student_id)
        if not student:
            raise StudentNotFoundException()

        student.admission_number = official_admission_number
        student.status = StudentStatus.ACTIVE
        student.is_active = True
        self.session.add(student)

        # Record timeline transition
        timeline = AdmissionTimeline(
            admission_id=admission.id,
            from_status=admission.status,
            to_status=AdmissionStatus.ENROLLED,
            action_by=user_id,
            remarks=remarks
            or f"Student successfully enrolled with Admission Number: {official_admission_number}",
        )
        await self.repo.create_timeline(timeline)

        # Update admission workflow details
        admission.status = AdmissionStatus.ENROLLED
        admission.admission_date = datetime.utcnow().date()
        self.session.add(admission)
        await self.session.flush()

        return admission
