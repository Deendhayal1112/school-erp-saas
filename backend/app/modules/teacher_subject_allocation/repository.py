import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.modules.employee.models import Employee
from app.modules.subject_management.models import Subject
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import (
    SubjectQualification,
    TeacherSubjectAllocation,
    TeacherWorkload,
)


class TeacherSubjectAllocationRepository:
    """
    Repository class executing optimized Async SQLAlchemy queries for allocations,
    workloads, and subject qualifications with tenant isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Allocations ---
    async def get_allocation(self, id: uuid.UUID, school_id: uuid.UUID) -> TeacherSubjectAllocation | None:
        stmt = select(TeacherSubjectAllocation).where(
            TeacherSubjectAllocation.id == id,
            TeacherSubjectAllocation.school_id == school_id,
            TeacherSubjectAllocation.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_teacher_allocation_match(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> TeacherSubjectAllocation | None:
        stmt = select(TeacherSubjectAllocation).where(
            TeacherSubjectAllocation.school_id == school_id,
            TeacherSubjectAllocation.teacher_id == teacher_id,
            TeacherSubjectAllocation.academic_year_id == academic_year_id,
            TeacherSubjectAllocation.term_id == term_id,
            TeacherSubjectAllocation.class_id == class_id,
            TeacherSubjectAllocation.section_id == section_id,
            TeacherSubjectAllocation.subject_id == subject_id,
            TeacherSubjectAllocation.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

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
        stmt = select(TeacherSubjectAllocation).where(
            TeacherSubjectAllocation.school_id == school_id,
            TeacherSubjectAllocation.is_deleted == False,
        )

        # Filters
        if teacher_id is not None:
            stmt = stmt.where(TeacherSubjectAllocation.teacher_id == teacher_id)
        if subject_id is not None:
            stmt = stmt.where(TeacherSubjectAllocation.subject_id == subject_id)
        if class_id is not None:
            stmt = stmt.where(TeacherSubjectAllocation.class_id == class_id)
        if section_id is not None:
            stmt = stmt.where(TeacherSubjectAllocation.section_id == section_id)
        if academic_year_id is not None:
            stmt = stmt.where(TeacherSubjectAllocation.academic_year_id == academic_year_id)
        if term_id is not None:
            stmt = stmt.where(TeacherSubjectAllocation.term_id == term_id)
        if status is not None:
            stmt = stmt.where(TeacherSubjectAllocation.status == status)
        if is_active is not None:
            stmt = stmt.where(TeacherSubjectAllocation.is_active == is_active)

        # Department join if filtering by department
        if department_id is not None:
            stmt = stmt.join(Teacher, TeacherSubjectAllocation.teacher_id == Teacher.id).join(
                Employee, Teacher.employee_id == Employee.id
            )
            stmt = stmt.where(Employee.department_id == department_id)

        # Sorting joins
        if sort_by == "teacher_name":
            # Joins: Allocation -> Teacher -> Employee
            stmt = (
                stmt.join(Teacher, TeacherSubjectAllocation.teacher_id == Teacher.id)
                .join(Employee, Teacher.employee_id == Employee.id)
                .order_by(Employee.first_name.asc(), Employee.last_name.asc())
            )
        elif sort_by == "subject":
            stmt = stmt.join(Subject, TeacherSubjectAllocation.subject_id == Subject.id).order_by(
                Subject.subject_name.asc()
            )
        elif sort_by == "priority":
            stmt = stmt.order_by(TeacherSubjectAllocation.priority.desc())
        else:
            stmt = stmt.order_by(TeacherSubjectAllocation.created_at.desc())

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_allocation(self, allocation: TeacherSubjectAllocation) -> TeacherSubjectAllocation:
        self.session.add(allocation)
        await self.session.flush()
        return allocation

    # --- Workloads ---
    async def get_workload(self, id: uuid.UUID, school_id: uuid.UUID) -> TeacherWorkload | None:
        stmt = select(TeacherWorkload).where(
            TeacherWorkload.id == id,
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_teacher_workload(self, school_id: uuid.UUID, teacher_id: uuid.UUID) -> TeacherWorkload | None:
        stmt = select(TeacherWorkload).where(
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.teacher_id == teacher_id,
            TeacherWorkload.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_workloads(
        self,
        school_id: uuid.UUID,
        teacher_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[TeacherWorkload]:
        stmt = select(TeacherWorkload).where(
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        if teacher_id is not None:
            stmt = stmt.where(TeacherWorkload.teacher_id == teacher_id)
        if is_active is not None:
            stmt = stmt.where(TeacherWorkload.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_workload(self, workload: TeacherWorkload) -> TeacherWorkload:
        self.session.add(workload)
        await self.session.flush()
        return workload

    # --- Qualifications ---
    async def get_qualification(self, id: uuid.UUID, school_id: uuid.UUID) -> SubjectQualification | None:
        stmt = select(SubjectQualification).where(
            SubjectQualification.id == id,
            SubjectQualification.school_id == school_id,
            SubjectQualification.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_teacher_subject_qualification(
        self, school_id: uuid.UUID, teacher_id: uuid.UUID, subject_id: uuid.UUID
    ) -> SubjectQualification | None:
        stmt = select(SubjectQualification).where(
            SubjectQualification.school_id == school_id,
            SubjectQualification.teacher_id == teacher_id,
            SubjectQualification.subject_id == subject_id,
            SubjectQualification.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

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
        stmt = select(SubjectQualification).where(
            SubjectQualification.school_id == school_id,
            SubjectQualification.is_deleted == False,
        )

        if teacher_id is not None:
            stmt = stmt.where(SubjectQualification.teacher_id == teacher_id)
        if subject_id is not None:
            stmt = stmt.where(SubjectQualification.subject_id == subject_id)
        if qualification_level is not None:
            stmt = stmt.where(SubjectQualification.qualification_level == qualification_level)
        if certified is not None:
            stmt = stmt.where(SubjectQualification.certified == certified)
        if is_active is not None:
            stmt = stmt.where(SubjectQualification.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def save_qualification(self, qual: SubjectQualification) -> SubjectQualification:
        self.session.add(qual)
        await self.session.flush()
        return qual
