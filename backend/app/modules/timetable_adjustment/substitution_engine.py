"""
Substitution Engine: automatically suggests available, qualified substitute teachers.

Ranking criteria (ascending score = better match):
 1. Qualified for the subject (TeacherSubjectAllocation)
 2. Free at the target slot (no existing ClassTimetableEntry)
 3. Same primary department as original teacher
 4. Lowest current weekly workload allocation
"""

import logging
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.class_timetable.models import ClassTimetableEntry
from app.modules.department.models import Department
from app.modules.employee.models import Employee
from app.modules.teacher.models import Teacher
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
    TeacherWorkload,
)
from app.modules.teacher_timetable.enums import TeacherAvailabilityStatus
from app.modules.teacher_timetable.models import TeacherAvailability
from app.modules.timetable_adjustment.constants import MAX_SUGGESTION_RESULTS
from app.modules.timetable_adjustment.schemas import SubstituteSuggestion

logger = logging.getLogger(__name__)


class SubstitutionEngine:
    """
    Searches for available, qualified substitute teachers ranked by suitability.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def suggest_substitutes(
        self,
        school_id: uuid.UUID,
        subject_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        original_teacher_id: uuid.UUID,
    ) -> list[SubstituteSuggestion]:
        """
        Returns a ranked list of substitute teacher suggestions.
        """
        # Step 1: Find all teachers qualified for this subject in this school
        alloc_stmt = select(TeacherSubjectAllocation).where(
            TeacherSubjectAllocation.school_id == school_id,
            TeacherSubjectAllocation.subject_id == subject_id,
            TeacherSubjectAllocation.teacher_id != original_teacher_id,
            TeacherSubjectAllocation.is_deleted == False,
        )
        allocs = (await self.db.execute(alloc_stmt)).scalars().all()
        qualified_teacher_ids = {a.teacher_id for a in allocs}

        if not qualified_teacher_ids:
            logger.info(
                "No qualified substitutes found for subject=%s school=%s",
                subject_id,
                school_id,
            )
            return []

        # Step 2: Filter out teachers already booked at this slot
        busy_stmt = select(ClassTimetableEntry.teacher_id).where(
            ClassTimetableEntry.teacher_id.in_(qualified_teacher_ids),
            ClassTimetableEntry.working_day_id == working_day_id,
            ClassTimetableEntry.time_slot_id == time_slot_id,
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.is_deleted == False,
        )
        busy_ids = set((await self.db.execute(busy_stmt)).scalars().all())

        # Step 3: Filter out teachers with unavailability blocks
        unavail_stmt = select(TeacherAvailability.teacher_id).where(
            TeacherAvailability.teacher_id.in_(qualified_teacher_ids),
            TeacherAvailability.working_day_id == working_day_id,
            TeacherAvailability.time_slot_id == time_slot_id,
            TeacherAvailability.school_id == school_id,
            TeacherAvailability.availability_status == TeacherAvailabilityStatus.UNAVAILABLE,
            TeacherAvailability.is_deleted == False,
        )
        unavail_ids = set((await self.db.execute(unavail_stmt)).scalars().all())

        available_ids = qualified_teacher_ids - busy_ids - unavail_ids
        if not available_ids:
            logger.info("All qualified substitutes are busy or unavailable.")
            return []

        # Step 4: Load teacher details and workload for ranking
        teacher_stmt = (
            select(Teacher)
            .where(
                Teacher.id.in_(available_ids),
                Teacher.school_id == school_id,
                Teacher.is_deleted == False,
            )
        )
        teachers = (await self.db.execute(teacher_stmt)).scalars().all()

        # Get original teacher's department for same-dept bonus
        orig_stmt = select(Teacher).where(
            Teacher.id == original_teacher_id,
            Teacher.school_id == school_id,
        )
        original_teacher = (await self.db.execute(orig_stmt)).scalar_one_or_none()
        orig_dept_id = original_teacher.primary_department_id if original_teacher else None

        # Load workloads
        workload_stmt = select(TeacherWorkload).where(
            TeacherWorkload.teacher_id.in_(available_ids),
            TeacherWorkload.school_id == school_id,
            TeacherWorkload.is_deleted == False,
        )
        workloads_raw = (await self.db.execute(workload_stmt)).scalars().all()
        workload_map: dict[uuid.UUID, TeacherWorkload] = {w.teacher_id: w for w in workloads_raw}

        # Load employee names
        emp_ids = [t.employee_id for t in teachers]
        emp_stmt = select(Employee).where(Employee.id.in_(emp_ids))
        emps = (await self.db.execute(emp_stmt)).scalars().all()
        emp_map: dict[uuid.UUID, Employee] = {e.id: e for e in emps}

        # Step 5: Score and rank
        suggestions: list[SubstituteSuggestion] = []
        for teacher in teachers:
            emp = emp_map.get(teacher.employee_id)
            teacher_name = (
                f"{emp.first_name} {emp.last_name}" if emp else str(teacher.id)
            )
            workload = workload_map.get(teacher.id)
            allocated = workload.allocated_periods if workload else 0
            max_periods = workload.maximum_weekly_periods if workload else 40
            remaining = max(0, max_periods - allocated)

            # Rank score: lower = better
            rank_score = allocated  # prefer less-loaded teachers
            if orig_dept_id and teacher.primary_department_id == orig_dept_id:
                rank_score -= 5  # bonus for same department

            suggestions.append(
                SubstituteSuggestion(
                    teacher_id=teacher.id,
                    teacher_name=teacher_name,
                    department=str(teacher.primary_department_id) if teacher.primary_department_id else None,
                    weekly_load=allocated,
                    remaining_capacity=remaining,
                    is_qualified=True,
                    suggestion_rank=rank_score,
                )
            )

        # Sort by rank score ascending, cap at MAX_SUGGESTION_RESULTS
        suggestions.sort(key=lambda s: s.suggestion_rank)
        # Re-assign sequential ranks 1..N
        for i, s in enumerate(suggestions[:MAX_SUGGESTION_RESULTS], start=1):
            s.suggestion_rank = i

        return suggestions[:MAX_SUGGESTION_RESULTS]
