import logging
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic_calendar.models import WorkingDay
from app.modules.class_timetable.enums import LessonType, TimetableStatus
from app.modules.class_timetable.models import ClassTimetable, ClassTimetableEntry
from app.modules.room.models import Room
from app.modules.section_management.models import Section
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
    TeacherWorkload,
)
from app.modules.teacher_timetable.models import TeacherAvailability
from app.modules.time_slot.models import TimeSlot
from app.modules.timetable_generator.constraint_engine import ConstraintEngine
from app.modules.timetable_generator.enums import JobStatus, ResultStatus
from app.modules.timetable_generator.exceptions import (
    TimetableGenerationFailedException,
)
from app.modules.timetable_generator.models import (
    GenerationJob,
    GenerationLog,
    GenerationResult,
)
from app.modules.timetable_generator.optimizer import TimetableOptimizer
from app.modules.timetable_generator.scheduler import TimetableScheduler

logger = logging.getLogger(__name__)


class TimetableGeneratorEngine:
    """
    Core engine that loads academic datasets, builds constraint mappings,
    runs the backtracking solver/optimizer, and persists the generated schedule.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(self, job_id: uuid.UUID) -> None:
        """
        Orchestrates loading data, running the solver, and saving the results
        under a single rollback-safe transaction.
        """
        start_time = time.time()

        # 1. Retrieve job details
        job_stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        job = (await self.db.execute(job_stmt)).scalar_one_or_none()
        if not job:
            logger.error(f"Generation job {job_id} not found.")
            return

        job.status = JobStatus.RUNNING
        await self.db.flush()

        await self._log(job_id, job.school_id, "INFO", "Started loading academic data configuration.")

        try:
            # 2. Load academic dataset
            school_id = job.school_id
            academic_year_id = job.academic_year_id
            term_id = job.term_id

            # Fetch working days (teaching days)
            wd_stmt = select(WorkingDay).where(
                WorkingDay.school_id == school_id,
                WorkingDay.academic_year_id == academic_year_id,
                WorkingDay.is_working == True,
                WorkingDay.is_deleted == False,
            )
            working_days = (await self.db.execute(wd_stmt)).scalars().all()
            if not working_days:
                raise ValueError("No active working days found for the academic year.")

            # Fetch teaching time slots (exclude breaks)
            ts_stmt = select(TimeSlot).where(
                TimeSlot.school_id == school_id,
                TimeSlot.academic_year_id == academic_year_id,
                TimeSlot.is_teaching == True,
                TimeSlot.is_break == False,
                TimeSlot.is_deleted == False,
            )
            time_slots = (await self.db.execute(ts_stmt)).scalars().all()
            if not time_slots:
                raise ValueError("No active teaching time slots found.")

            # Build display order dictionary
            slot_orders = {ts.id: ts.display_order for ts in time_slots}

            # Fetch rooms
            room_stmt = select(Room).where(
                Room.school_id == school_id,
                Room.is_active == True,
                Room.is_deleted == False,
            )
            rooms = (await self.db.execute(room_stmt)).scalars().all()
            if not rooms:
                raise ValueError("No active rooms found.")

            # Fetch teacher subject allocations
            alloc_stmt = select(TeacherSubjectAllocation).where(
                TeacherSubjectAllocation.school_id == school_id,
                TeacherSubjectAllocation.academic_year_id == academic_year_id,
                TeacherSubjectAllocation.term_id == term_id,
                TeacherSubjectAllocation.status == "ACTIVE",
                TeacherSubjectAllocation.is_deleted == False,
            )
            allocations = (await self.db.execute(alloc_stmt)).scalars().all()
            if not allocations:
                raise ValueError("No active teacher subject allocations found.")

            # Fetch teacher workloads
            wl_stmt = select(TeacherWorkload).where(
                TeacherWorkload.school_id == school_id,
                TeacherWorkload.is_deleted == False,
            )
            workloads = (await self.db.execute(wl_stmt)).scalars().all()

            # Fetch custom teacher availability
            avail_stmt = select(TeacherAvailability).where(
                TeacherAvailability.school_id == school_id,
                TeacherAvailability.is_deleted == False,
            )
            availabilities = (await self.db.execute(avail_stmt)).scalars().all()

            # Fetch section capacity
            sect_stmt = select(Section).where(
                Section.school_id == school_id,
                Section.academic_year_id == academic_year_id,
                Section.is_deleted == False,
            )
            sections = (await self.db.execute(sect_stmt)).scalars().all()

            await self._log(
                job_id,
                school_id,
                "INFO",
                f"Dataset loaded: {len(working_days)} working days, {len(time_slots)} time slots, "
                f"{len(rooms)} rooms, {len(allocations)} allocations, {len(workloads)} workloads.",
            )

            # 3. Construct structures for Constraint Engine
            # availabilities map: (teacher_id, day_id, slot_id) -> status
            avail_map = {}
            for a in availabilities:
                avail_map[(a.teacher_id, a.working_day_id, a.time_slot_id)] = a.availability_status.value

            # workloads map: teacher_id -> limit configurations
            wl_map = {}
            for w in workloads:
                wl_map[w.teacher_id] = {
                    "max_weekly": w.maximum_weekly_periods,
                    "daily_limit": w.daily_limit,
                    "consecutive_period_limit": w.consecutive_period_limit,
                }

            room_caps = {r.id: r.capacity for r in rooms}
            sect_caps = {s.id: s.capacity for s in sections}

            # room preferences resolved from allocations
            pref_rooms = {}
            for al in allocations:
                if al.preferred_room_id:
                    pref_rooms[(al.teacher_id, al.subject_id)] = al.preferred_room_id

            # slots list
            available_slots = []
            for wd in working_days:
                for ts in time_slots:
                    if ts.working_day_id == wd.id:
                        available_slots.append((wd.id, ts.id))

            # required variables to solve (expanded from allocations based on weekly period requirement)
            required_variables = []
            for al in allocations:
                limit = al.weekly_period_limit or 5
                for _ in range(limit):
                    required_variables.append(
                        {
                            "teacher_id": al.teacher_id,
                            "subject_id": al.subject_id,
                            "class_id": al.class_id,
                            "section_id": al.section_id,
                            "lesson_type": "THEORY",  # default
                            "allocation_id": al.id,
                        }
                    )

            # Update job info
            job.total_teachers = len({al.teacher_id for al in allocations})
            job.total_classes = len({al.class_id for al in allocations})
            job.total_subjects = len({al.subject_id for al in allocations})
            await self.db.flush()

            # 4. Instantiate engines
            engine = ConstraintEngine(
                teacher_availabilities=avail_map,
                teacher_workloads=wl_map,
                room_capacities=room_caps,
                section_capacities=sect_caps,
                preferred_rooms=pref_rooms,
                time_slot_orders=slot_orders,
            )

            scheduler = TimetableScheduler(
                constraint_engine=engine,
                available_slots=available_slots,
                rooms=[r.id for r in rooms],
            )

            await self._log(job_id, school_id, "INFO", f"Triggered backtracking scheduler for {len(required_variables)} periods.")

            # 5. Run Scheduler
            solution = scheduler.solve(required_variables, timeout_seconds=50.0)
            if not solution:
                raise TimetableGenerationFailedException(
                    "Backtracking scheduler failed to find a conflict-free solution satisfying all hard constraints."
                )

            await self._log(job_id, school_id, "INFO", f"Backtracking search completed successfully. Solved in {scheduler.iterations} iterations.")

            # 6. Optimize schedule
            optimizer = TimetableOptimizer(constraint_engine=engine)
            optimized_solution = optimizer.optimize(solution, max_iterations=200)

            # 7. Persist the generated timetable entries
            await self._log(job_id, school_id, "INFO", "Persisting generated timetable allocations to database.")
            generated_timetable_ids = await self._persist_schedule(
                school_id=school_id,
                academic_year_id=academic_year_id,
                term_id=term_id,
                job_name=job.job_name,
                schedule=optimized_solution,
                slot_orders=slot_orders,
            )

            # 8. Record success metrics
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.execution_time = time.time() - start_time
            job.generated_entries = len(optimized_solution)
            job.failed_entries = 0
            await self.db.flush()

            # Save result entry
            final_score = engine.calculate_score(optimized_solution)
            for tt_id in generated_timetable_ids:
                result_obj = GenerationResult(
                    generation_job_id=job.id,
                    school_id=school_id,
                    timetable_id=tt_id,
                    status=ResultStatus.SUCCESS,
                    score=final_score,
                    data={"total_entries": len(optimized_solution), "final_score": final_score},
                )
                self.db.add(result_obj)

            await self._log(
                job_id,
                school_id,
                "INFO",
                f"Timetable generation completed successfully in {job.execution_time:.2f} seconds. Score: {final_score}",
            )

        except Exception as e:
            logger.exception("Automatic timetable generation failed.")
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.execution_time = time.time() - start_time
            job.remarks = str(e)
            await self.db.flush()

            await self._log(job_id, job.school_id, "ERROR", f"Job failed: {e!s}")

            # Save result failure log
            result_obj = GenerationResult(
                generation_job_id=job.id,
                school_id=job.school_id,
                status=ResultStatus.FAILED,
                score=0.0,
                data={"error": str(e)},
            )
            self.db.add(result_obj)
            raise

    async def _log(
        self, job_id: uuid.UUID, school_id: uuid.UUID, log_level: str, message: str
    ) -> None:
        """Helper to create generation logs."""
        log = GenerationLog(
            generation_job_id=job_id,
            school_id=school_id,
            log_level=log_level,
            message=message,
        )
        self.db.add(log)
        await self.db.flush()

    async def _persist_schedule(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        job_name: str,
        schedule: list[dict[str, Any]],
        slot_orders: dict[uuid.UUID, int],
    ) -> list[uuid.UUID]:
        """
        Creates or updates ClassTimetables and adds ClassTimetableEntry rows.
        """
        # Group schedule by class/section
        grouped_schedule: dict[tuple[uuid.UUID, uuid.UUID], list[dict[str, Any]]] = {}
        for entry in schedule:
            key = (entry["class_id"], entry["section_id"])
            if key not in grouped_schedule:
                grouped_schedule[key] = []
            grouped_schedule[key].append(entry)

        timetable_ids = []

        for (class_id, section_id), entries in grouped_schedule.items():
            # Check if there is an existing draft class timetable for this section
            stmt = select(ClassTimetable).where(
                ClassTimetable.school_id == school_id,
                ClassTimetable.class_id == class_id,
                ClassTimetable.section_id == section_id,
                ClassTimetable.academic_year_id == academic_year_id,
                ClassTimetable.term_id == term_id,
                ClassTimetable.status == TimetableStatus.DRAFT,
                ClassTimetable.is_deleted == False,
            )
            timetable = (await self.db.execute(stmt)).scalar_one_or_none()

            if timetable:
                # If draft exists, delete its entries to overwrite cleanly
                del_stmt = select(ClassTimetableEntry).where(
                    ClassTimetableEntry.timetable_id == timetable.id,
                    ClassTimetableEntry.school_id == school_id,
                    ClassTimetableEntry.is_deleted == False,
                )
                existing_entries = (await self.db.execute(del_stmt)).scalars().all()
                for ee in existing_entries:
                    ee.is_deleted = True
                    self.db.add(ee)
            else:
                # Create a new draft timetable
                timetable = ClassTimetable(
                    school_id=school_id,
                    class_id=class_id,
                    section_id=section_id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    name=f"Auto Generated {job_name}",
                    effective_from=datetime.utcnow().date(),
                    status=TimetableStatus.DRAFT,
                )
                self.db.add(timetable)
                await self.db.flush()

            timetable_ids.append(timetable.id)

            # Persist each period entry
            # Sort entries by slot displaying order to assign period numbers
            entries.sort(key=lambda x: slot_orders.get(x["time_slot_id"], 0))

            for idx, entry in enumerate(entries):
                # Retrieve teacher subject allocation if available
                alloc_stmt = select(TeacherSubjectAllocation.id).where(
                    TeacherSubjectAllocation.teacher_id == entry["teacher_id"],
                    TeacherSubjectAllocation.subject_id == entry["subject_id"],
                    TeacherSubjectAllocation.class_id == class_id,
                    TeacherSubjectAllocation.section_id == section_id,
                    TeacherSubjectAllocation.school_id == school_id,
                    TeacherSubjectAllocation.is_deleted == False,
                )
                alloc_id = (await self.db.execute(alloc_stmt)).scalar()

                cte = ClassTimetableEntry(
                    school_id=school_id,
                    timetable_id=timetable.id,
                    working_day_id=entry["working_day_id"],
                    time_slot_id=entry["time_slot_id"],
                    teacher_subject_allocation_id=alloc_id,
                    teacher_id=entry["teacher_id"],
                    subject_id=entry["subject_id"],
                    room_id=entry.get("room_id"),
                    period_number=idx + 1,
                    lesson_type=LessonType.THEORY,
                )
                self.db.add(cte)

        await self.db.flush()
        return timetable_ids
