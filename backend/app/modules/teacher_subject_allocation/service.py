import logging
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.exceptions.exceptions import NotFoundException
from app.models.class_model import SchoolClass
from app.models.user import User
from app.modules.academic_year.exceptions import AcademicYearNotFoundException
from app.modules.academic_year.models import AcademicYear
from app.modules.room.exceptions import RoomNotFoundException
from app.modules.room.models import Room
from app.modules.section_management.exceptions import SectionNotFoundException
from app.modules.section_management.models import Section
from app.modules.staff_attendance.models import AttendanceShift
from app.modules.subject_management.exceptions import SubjectNotFoundException
from app.modules.subject_management.models import Subject
from app.modules.teacher.exceptions import TeacherNotFoundException
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.constants import ALLOCATION_CACHE_TTL
from app.modules.teacher_subject_allocation.enums import AllocationStatus
from app.modules.teacher_subject_allocation.exceptions import (
    DuplicateAllocationException,
    SubjectQualificationNotFoundException,
    TeacherNotQualifiedException,
    TeacherSubjectAllocationNotFoundException,
    TeacherWorkloadNotFoundException,
)
from app.modules.teacher_subject_allocation.models import (
    SubjectQualification,
    TeacherSubjectAllocation,
    TeacherWorkload,
)
from app.modules.teacher_subject_allocation.repository import TeacherSubjectAllocationRepository
from app.modules.teacher_subject_allocation.schemas import (
    SubjectQualificationCreate,
    SubjectQualificationUpdate,
    TeacherAssignmentSummaryResponse,
    TeacherSubjectAllocationCreate,
    TeacherSubjectAllocationUpdate,
    TeacherWorkloadCreate,
    TeacherWorkloadUpdate,
)
from app.modules.teacher_subject_allocation.validators import (
    validate_allocation_dates,
    validate_workload_capacity,
)
from app.modules.term.exceptions import TermNotFoundException
from app.modules.term.models import Term
from app.modules.time_slot.exceptions import ClassNotFoundException

logger = logging.getLogger(__name__)


class TeacherSubjectAllocationService:
    """
    Service layer executing business logic for allocations, workload calculations,
    subject qualifications checking, cache clearing, and audit logging.
    """

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self.db = db
        self.repo = TeacherSubjectAllocationRepository(db)
        self.audit = AuditLogService(db)
        self.cache = cache or CacheService()

    async def _clear_caches(self, school_id: uuid.UUID) -> None:
        await self.cache.delete_pattern(f"allocation:list:{school_id}:*")
        await self.cache.delete_pattern(f"workload:list:{school_id}:*")
        await self.cache.delete_pattern(f"qualification:list:{school_id}:*")
        await self.cache.delete_pattern(f"teacher:summary:{school_id}:*")

    # ===========================================================================
    # REFERENCE VERIFICATIONS
    # ===========================================================================

    async def _verify_entities_exist(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
        subject_id: uuid.UUID,
        preferred_room_id: uuid.UUID | None = None,
        preferred_shift_id: uuid.UUID | None = None,
    ) -> None:
        # Teacher
        t_stmt = select(Teacher).where(Teacher.id == teacher_id, Teacher.school_id == school_id, Teacher.is_deleted == False)
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TeacherNotFoundException()

        # Academic Year
        ay_stmt = select(AcademicYear).where(
            AcademicYear.id == academic_year_id, AcademicYear.school_id == school_id, AcademicYear.is_deleted == False
        )
        if not (await self.db.execute(ay_stmt)).scalar_one_or_none():
            raise AcademicYearNotFoundException()

        # Term
        tm_stmt = select(Term).where(Term.id == term_id, Term.school_id == school_id, Term.is_deleted == False)
        if not (await self.db.execute(tm_stmt)).scalar_one_or_none():
            raise TermNotFoundException()

        # Class
        c_stmt = select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.school_id == school_id, SchoolClass.is_deleted == False)
        if not (await self.db.execute(c_stmt)).scalar_one_or_none():
            raise ClassNotFoundException()

        # Section
        s_stmt = select(Section).where(
            Section.id == section_id, Section.school_id == school_id, Section.class_id == class_id, Section.is_deleted == False
        )
        if not (await self.db.execute(s_stmt)).scalar_one_or_none():
            raise SectionNotFoundException()

        # Subject
        sub_stmt = select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id, Subject.is_deleted == False)
        if not (await self.db.execute(sub_stmt)).scalar_one_or_none():
            raise SubjectNotFoundException()

        # Preferred Room (Optional)
        if preferred_room_id is not None:
            r_stmt = select(Room).where(Room.id == preferred_room_id, Room.school_id == school_id, Room.is_deleted == False)
            if not (await self.db.execute(r_stmt)).scalar_one_or_none():
                raise RoomNotFoundException()

        # Preferred Shift (Optional)
        if preferred_shift_id is not None:
            sf_stmt = select(AttendanceShift).where(
                AttendanceShift.id == preferred_shift_id, AttendanceShift.school_id == school_id, AttendanceShift.is_deleted == False
            )
            if not (await self.db.execute(sf_stmt)).scalar_one_or_none():
                raise NotFoundException("Preferred attendance shift not found.")

    async def _verify_qualification(self, school_id: uuid.UUID, teacher_id: uuid.UUID, subject_id: uuid.UUID) -> None:
        qual = await self.repo.get_teacher_subject_qualification(school_id, teacher_id, subject_id)
        if not qual or not qual.certified:
            raise TeacherNotQualifiedException("Teacher does not hold active certification for this subject.")

    # ===========================================================================
    # WORKLOAD AUTO-PROVISIONING
    # ===========================================================================

    async def _get_or_create_workload(self, school_id: uuid.UUID, teacher_id: uuid.UUID) -> TeacherWorkload:
        workload = await self.repo.get_teacher_workload(school_id, teacher_id)
        if not workload:
            # Provision default teacher workload
            workload = TeacherWorkload(
                school_id=school_id,
                teacher_id=teacher_id,
                maximum_weekly_periods=24,
                allocated_periods=0,
                remaining_periods=24,
                daily_limit=5,
                consecutive_period_limit=3,
                is_active=True,
            )
            await self.repo.save_workload(workload)
            await self.db.flush()
        return workload

    # ===========================================================================
    # ALLOCATIONS
    # ===========================================================================

    async def get_allocation(self, id: uuid.UUID, school_id: uuid.UUID) -> TeacherSubjectAllocation:
        alloc = await self.repo.get_allocation(id, school_id)
        if not alloc:
            raise TeacherSubjectAllocationNotFoundException()
        return alloc

    async def list_allocations(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        status: str | None = None,
        is_active: bool | None = None,
        sort_by: str = "teacher_name",
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[TeacherSubjectAllocation]:
        allocs = await self.repo.list_allocations(
            school_id=school_id,
            teacher_id=teacher_id,
            department_id=department_id,
            subject_id=subject_id,
            class_id=class_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            status=status,
            is_active=is_active,
            sort_by=sort_by,
            skip=skip,
            limit=limit,
        )
        for a in allocs:
            await self.db.refresh(a)
        return allocs

    async def allocate_subject(
        self, school_id: uuid.UUID, data: TeacherSubjectAllocationCreate, actor: User
    ) -> TeacherSubjectAllocation:
        validate_allocation_dates(data.effective_from, data.effective_to)

        # Entity existences
        await self._verify_entities_exist(
            school_id=school_id,
            teacher_id=data.teacher_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
            preferred_room_id=data.preferred_room_id,
            preferred_shift_id=data.preferred_shift_id,
        )

        # Certification qualification verification
        await self._verify_qualification(school_id, data.teacher_id, data.subject_id)

        # Check duplicate allocation
        dup = await self.repo.get_teacher_allocation_match(
            school_id=school_id,
            teacher_id=data.teacher_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
        )
        if dup:
            raise DuplicateAllocationException()

        # Workload calculation & validation
        workload = await self._get_or_create_workload(school_id, data.teacher_id)
        validate_workload_capacity(workload.allocated_periods, data.weekly_period_limit, workload.maximum_weekly_periods)

        # Allocate periods
        workload.allocated_periods += data.weekly_period_limit
        workload.remaining_periods = workload.maximum_weekly_periods - workload.allocated_periods
        await self.repo.save_workload(workload)

        alloc = TeacherSubjectAllocation(
            school_id=school_id,
            teacher_id=data.teacher_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
            priority=data.priority,
            weekly_period_limit=data.weekly_period_limit,
            assigned_periods=data.weekly_period_limit,
            preferred_room_id=data.preferred_room_id,
            preferred_shift_id=data.preferred_shift_id,
            is_class_teacher=data.is_class_teacher,
            is_primary_teacher=data.is_primary_teacher,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            remarks=data.remarks,
            status=data.status,
            is_active=True,
            is_locked=False,
            created_by=actor.id,
            updated_by=actor.id,
        )
        await self.repo.save_allocation(alloc)
        await self.db.flush()
        await self.db.refresh(alloc)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_subject_allocation",
            action="allocation.create",
            entity_name="TeacherSubjectAllocation",
            entity_id=alloc.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return alloc

    async def update_allocation(
        self, id: uuid.UUID, school_id: uuid.UUID, data: TeacherSubjectAllocationUpdate, actor: User
    ) -> TeacherSubjectAllocation:
        alloc = await self.get_allocation(id, school_id)

        # Date validations
        new_from = data.effective_from if data.effective_from is not None else alloc.effective_from
        new_to = data.effective_to if data.effective_to is not None else alloc.effective_to
        validate_allocation_dates(new_from, new_to)

        # Entity existences check if referencing preferred rooms/shifts change
        if data.preferred_room_id is not None:
            r_stmt = select(Room).where(Room.id == data.preferred_room_id, Room.school_id == school_id, Room.is_deleted == False)
            if not (await self.db.execute(r_stmt)).scalar_one_or_none():
                raise RoomNotFoundException()
            alloc.preferred_room_id = data.preferred_room_id

        if data.preferred_shift_id is not None:
            sf_stmt = select(AttendanceShift).where(
                AttendanceShift.id == data.preferred_shift_id, AttendanceShift.school_id == school_id, AttendanceShift.is_deleted == False
            )
            if not (await self.db.execute(sf_stmt)).scalar_one_or_none():
                raise NotFoundException("Preferred attendance shift not found.")
            alloc.preferred_shift_id = data.preferred_shift_id

        # Recalculate periods workload
        if data.weekly_period_limit is not None and data.weekly_period_limit != alloc.weekly_period_limit:
            workload = await self._get_or_create_workload(school_id, alloc.teacher_id)
            current_allocated_sans_this = workload.allocated_periods - alloc.weekly_period_limit
            validate_workload_capacity(current_allocated_sans_this, data.weekly_period_limit, workload.maximum_weekly_periods)

            # Re-allocate
            workload.allocated_periods = current_allocated_sans_this + data.weekly_period_limit
            workload.remaining_periods = workload.maximum_weekly_periods - workload.allocated_periods
            await self.repo.save_workload(workload)

            alloc.weekly_period_limit = data.weekly_period_limit
            alloc.assigned_periods = data.weekly_period_limit

        # Apply other updates
        if data.priority is not None:
            alloc.priority = data.priority
        if data.is_class_teacher is not None:
            alloc.is_class_teacher = data.is_class_teacher
        if data.is_primary_teacher is not None:
            alloc.is_primary_teacher = data.is_primary_teacher
        if data.effective_from is not None:
            alloc.effective_from = data.effective_from
        if data.effective_to is not None:
            alloc.effective_to = data.effective_to
        if data.remarks is not None:
            alloc.remarks = data.remarks
        if data.status is not None:
            alloc.status = data.status
        if data.is_active is not None:
            alloc.is_active = data.is_active

        alloc.updated_by = actor.id
        await self.repo.save_allocation(alloc)
        await self.db.flush()
        await self.db.refresh(alloc)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_subject_allocation",
            action="allocation.update",
            entity_name="TeacherSubjectAllocation",
            entity_id=alloc.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return alloc

    async def remove_allocation(self, id: uuid.UUID, school_id: uuid.UUID, actor: User) -> None:
        alloc = await self.get_allocation(id, school_id)

        # Deallocate workload periods
        workload = await self._get_or_create_workload(school_id, alloc.teacher_id)
        workload.allocated_periods = max(0, workload.allocated_periods - alloc.weekly_period_limit)
        workload.remaining_periods = workload.maximum_weekly_periods - workload.allocated_periods
        await self.repo.save_workload(workload)

        # Soft delete allocation
        alloc.is_deleted = True
        alloc.updated_by = actor.id
        await self.repo.save_allocation(alloc)
        await self.db.flush()

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_subject_allocation",
            action="allocation.delete",
            entity_name="TeacherSubjectAllocation",
            entity_id=alloc.id,
            user_id=actor.id,
            school_id=school_id,
        )

    # ===========================================================================
    # WORKLOADS
    # ===========================================================================

    async def get_workload(self, id: uuid.UUID, school_id: uuid.UUID) -> TeacherWorkload:
        wk = await self.repo.get_workload(id, school_id)
        if not wk:
            raise TeacherWorkloadNotFoundException()
        return wk

    async def list_workloads(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[TeacherWorkload]:
        wks = await self.repo.list_workloads(school_id, teacher_id, is_active, skip, limit)
        for w in wks:
            await self.db.refresh(w)
        return wks

    async def create_workload(
        self, school_id: uuid.UUID, data: TeacherWorkloadCreate, actor: User
    ) -> TeacherWorkload:
        # Check teacher exists
        t_stmt = select(Teacher).where(Teacher.id == data.teacher_id, Teacher.school_id == school_id, Teacher.is_deleted == False)
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TeacherNotFoundException()

        # Check duplicate configuration
        existing = await self.repo.get_teacher_workload(school_id, data.teacher_id)
        if existing:
            raise DuplicateAllocationException("Teacher workload configuration already exists.")

        wk = TeacherWorkload(
            school_id=school_id,
            teacher_id=data.teacher_id,
            maximum_weekly_periods=data.maximum_weekly_periods,
            allocated_periods=data.allocated_periods,
            remaining_periods=data.maximum_weekly_periods - data.allocated_periods,
            daily_limit=data.daily_limit,
            consecutive_period_limit=data.consecutive_period_limit,
            is_active=True,
        )
        await self.repo.save_workload(wk)
        await self.db.flush()
        await self.db.refresh(wk)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_subject_allocation",
            action="workload.update",
            entity_name="TeacherWorkload",
            entity_id=wk.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return wk

    async def update_workload(
        self, id: uuid.UUID, school_id: uuid.UUID, data: TeacherWorkloadUpdate, actor: User
    ) -> TeacherWorkload:
        wk = await self.get_workload(id, school_id)

        new_max = data.maximum_weekly_periods if data.maximum_weekly_periods is not None else wk.maximum_weekly_periods
        new_allocated = data.allocated_periods if data.allocated_periods is not None else wk.allocated_periods

        if new_allocated > new_max:
            raise WeeklyWorkloadExceededException("Allocated periods cannot exceed maximum weekly periods capacity.")

        if data.maximum_weekly_periods is not None:
            wk.maximum_weekly_periods = data.maximum_weekly_periods
        if data.allocated_periods is not None:
            wk.allocated_periods = data.allocated_periods

        wk.remaining_periods = wk.maximum_weekly_periods - wk.allocated_periods

        if data.daily_limit is not None:
            wk.daily_limit = data.daily_limit
        if data.consecutive_period_limit is not None:
            wk.consecutive_period_limit = data.consecutive_period_limit
        if data.is_active is not None:
            wk.is_active = data.is_active

        await self.repo.save_workload(wk)
        await self.db.flush()
        await self.db.refresh(wk)

        await self._clear_caches(school_id)

        await self.audit.log_action(
            module="teacher_subject_allocation",
            action="workload.update",
            entity_name="TeacherWorkload",
            entity_id=wk.id,
            user_id=actor.id,
            school_id=school_id,
        )
        return wk

    # ===========================================================================
    # QUALIFICATIONS
    # ===========================================================================

    async def get_qualification(self, id: uuid.UUID, school_id: uuid.UUID) -> SubjectQualification:
        q = await self.repo.get_qualification(id, school_id)
        if not q:
            raise SubjectQualificationNotFoundException()
        return q

    async def list_qualifications(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        qualification_level: str | None = None,
        certified: bool | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[SubjectQualification]:
        qs = await self.repo.list_qualifications(
            school_id, teacher_id, subject_id, qualification_level, certified, is_active, skip, limit
        )
        for q in qs:
            await self.db.refresh(q)
        return qs

    async def create_qualification(
        self, school_id: uuid.UUID, data: SubjectQualificationCreate, actor: User
    ) -> SubjectQualification:
        # Check teacher
        t_stmt = select(Teacher).where(Teacher.id == data.teacher_id, Teacher.school_id == school_id, Teacher.is_deleted == False)
        if not (await self.db.execute(t_stmt)).scalar_one_or_none():
            raise TeacherNotFoundException()

        # Check subject
        sub_stmt = select(Subject).where(Subject.id == data.subject_id, Subject.school_id == school_id, Subject.is_deleted == False)
        if not (await self.db.execute(sub_stmt)).scalar_one_or_none():
            raise SubjectNotFoundException()

        # Check duplicate qualification link
        existing = await self.repo.get_teacher_subject_qualification(school_id, data.teacher_id, data.subject_id)
        if existing:
            raise DuplicateAllocationException("Subject qualification already exists for this teacher.")

        qual = SubjectQualification(
            school_id=school_id,
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            qualification_level=data.qualification_level,
            certified=data.certified,
            years_of_experience=data.years_of_experience,
            is_active=True,
        )
        await self.repo.save_qualification(qual)
        await self.db.flush()
        await self.db.refresh(qual)

        await self._clear_caches(school_id)
        return qual

    async def update_qualification(
        self, id: uuid.UUID, school_id: uuid.UUID, data: SubjectQualificationUpdate, actor: User
    ) -> SubjectQualification:
        qual = await self.get_qualification(id, school_id)

        if data.qualification_level is not None:
            qual.qualification_level = data.qualification_level
        if data.certified is not None:
            qual.certified = data.certified
        if data.years_of_experience is not None:
            qual.years_of_experience = data.years_of_experience
        if data.is_active is not None:
            qual.is_active = data.is_active

        await self.repo.save_qualification(qual)
        await self.db.flush()
        await self.db.refresh(qual)

        await self._clear_caches(school_id)
        return qual

    async def delete_qualification(self, id: uuid.UUID, school_id: uuid.UUID, actor: User) -> None:
        qual = await self.get_qualification(id, school_id)
        qual.is_deleted = True

        await self.repo.save_qualification(qual)
        await self.db.flush()

        await self._clear_caches(school_id)

    # ===========================================================================
    # SUMMARIES
    # ===========================================================================

    async def generate_teacher_assignment_summary(
        self, teacher_id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherAssignmentSummaryResponse:
        # Load teacher profile with employee relationship
        t_stmt = (
            select(Teacher)
            .options(joinedload(Teacher.employee))
            .where(Teacher.id == teacher_id, Teacher.school_id == school_id, Teacher.is_deleted == False)
        )
        teacher_res = await self.db.execute(t_stmt)
        teacher = teacher_res.scalar_one_or_none()
        if not teacher:
            raise TeacherNotFoundException()

        # Load workload
        wk = await self._get_or_create_workload(school_id, teacher_id)

        # Load allocations
        allocs = await self.list_allocations(school_id=school_id, teacher_id=teacher_id)

        employee_profile = teacher.employee
        full_name = f"{employee_profile.first_name} {employee_profile.last_name}"

        return TeacherAssignmentSummaryResponse(
            teacher_id=teacher.id,
            teacher_name=full_name,
            teacher_code=teacher.teacher_code,
            max_weekly_periods=wk.maximum_weekly_periods,
            allocated_periods=wk.allocated_periods,
            remaining_periods=wk.remaining_periods,
            assigned_subjects_count=len(allocs),
            allocations=list(allocs),
        )
