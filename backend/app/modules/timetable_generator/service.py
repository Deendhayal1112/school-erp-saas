import asyncio
import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.db.session import AsyncSessionLocal
from app.exceptions.exceptions import NotFoundException
from app.models.user import User
from app.modules.academic_calendar.models import WorkingDay
from app.modules.teacher_subject_allocation.models import (
    TeacherSubjectAllocation,
    TeacherWorkload,
)
from app.modules.time_slot.models import TimeSlot
from app.modules.timetable_generator.enums import JobStatus, ResultStatus
from app.modules.timetable_generator.exceptions import (
    ActiveJobRunningException,
    GenerationJobNotFoundException,
)
from app.modules.timetable_generator.generator import TimetableGeneratorEngine
from app.modules.timetable_generator.models import (
    GenerationJob,
    GenerationLog,
    GenerationResult,
)
from app.modules.timetable_generator.repository import TimetableGeneratorRepository
from app.modules.timetable_generator.schemas import (
    ConstraintViolation,
    GenerateTimetableRequest,
    ValidationRequest,
    ValidationResponse,
)
from app.modules.timetable_generator.validators import validate_generation_params

logger = logging.getLogger(__name__)


class TimetableGeneratorService:
    """
    High-level orchestrator service controlling generation jobs, asynchronous task running,
    dry-run validators, cache updates, and audit logging.
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: TimetableGeneratorRepository | None = None,
        cache: CacheService | None = None,
        audit: AuditLogService | None = None,
    ) -> None:
        self.db = db
        self.repo = repo or TimetableGeneratorRepository(db)
        self.cache = cache or CacheService()
        self.audit = audit or AuditLogService(db)
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def _clear_timetable_caches(self, school_id: uuid.UUID) -> None:
        await self.cache.delete_pattern(f"class_timetable:list:{school_id}:*")
        await self.cache.delete_pattern(f"class_timetable:weekly:{school_id}:*")
        await self.cache.delete_pattern(f"teacher_timetable:list:{school_id}:*")
        await self.cache.delete_pattern(f"teacher_timetable:weekly:{school_id}:*")

    async def get_job(self, job_id: uuid.UUID, school_id: uuid.UUID) -> GenerationJob:
        job = await self.repo.get_job(job_id, school_id)
        if not job:
            raise GenerationJobNotFoundException()
        return job

    async def get_result(self, job_id: uuid.UUID, school_id: uuid.UUID) -> GenerationResult:
        res = await self.repo.get_result_by_job(job_id, school_id)
        if not res:
            raise NotFoundException("Result not found for this generation job.")
        return res

    async def get_logs(self, job_id: uuid.UUID, school_id: uuid.UUID) -> Sequence[GenerationLog]:
        return await self.repo.get_logs_by_job(job_id, school_id)

    async def trigger_generation(
        self, school_id: uuid.UUID, data: GenerateTimetableRequest, actor: User
    ) -> GenerationJob:
        validate_generation_params(school_id, data.academic_year_id, data.term_id)

        # 1. Check if there is an active running job
        active_job = await self.repo.get_active_running_job(school_id, data.term_id)
        if active_job:
            raise ActiveJobRunningException()

        # 2. Create job record
        job = GenerationJob(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            job_name=data.job_name,
            status=JobStatus.PENDING,
            remarks="Task queued.",
        )
        await self.repo.save_job(job)
        await self.db.commit()

        # 3. Log audit event
        await self.audit.log_action(
            module="timetable_generator",
            action="generation.started",
            entity_name="GenerationJob",
            entity_id=job.id,
            user_id=actor.id,
            school_id=school_id,
        )

        # 4. Trigger asynchronous generator task in background
        task = asyncio.create_task(self.run_generation_task(job.id, actor.id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return job

    async def run_generation_task(self, job_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        """
        Background worker task running generator engine inside a clean database session context.
        """
        async with AsyncSessionLocal() as session:
            try:
                engine = TimetableGeneratorEngine(session)
                await engine.generate(job_id)
                await session.commit()

                # Fetch job details to clear cache and log audit on success
                job_stmt = select(GenerationJob).where(GenerationJob.id == job_id)
                job = (await session.execute(job_stmt)).scalar_one_or_none()
                if job:
                    await self._clear_timetable_caches(job.school_id)
                    audit_srv = AuditLogService(session)
                    await audit_srv.log_action(
                        module="timetable_generator",
                        action="generation.completed",
                        entity_name="GenerationJob",
                        entity_id=job.id,
                        user_id=actor_id,
                        school_id=job.school_id,
                    )
                    await session.commit()
            except Exception as e:
                logger.exception(f"Background timetable generation failed for job {job_id}.")
                await session.rollback()

                # Record audit failure log
                async with AsyncSessionLocal() as fail_session:
                    job_stmt = select(GenerationJob).where(GenerationJob.id == job_id)
                    job = (await fail_session.execute(job_stmt)).scalar_one_or_none()
                    if job:
                        job.status = JobStatus.FAILED
                        job.remarks = f"Error during generation execution: {e!s}"
                        fail_session.add(job)

                        # Write generation log fail row
                        glog = GenerationLog(
                            generation_job_id=job_id,
                            school_id=job.school_id,
                            log_level="ERROR",
                            message=f"Generation failed: {e!s}",
                        )
                        fail_session.add(glog)

                        # Write generation result fail row
                        gres = GenerationResult(
                            generation_job_id=job_id,
                            school_id=job.school_id,
                            status=ResultStatus.FAILED,
                            score=0.0,
                            data={"error": str(e)},
                        )
                        fail_session.add(gres)

                        audit_srv = AuditLogService(fail_session)
                        await audit_srv.log_action(
                            module="timetable_generator",
                            action="generation.failed",
                            entity_name="GenerationJob",
                            entity_id=job.id,
                            user_id=actor_id,
                            school_id=job.school_id,
                        )
                        await fail_session.commit()

    # --- Dry Run Setup Validator ---
    async def validate_timetable_setup(
        self, school_id: uuid.UUID, data: ValidationRequest
    ) -> ValidationResponse:
        """
        Runs dry-run check on current constraints setup to report potential conflicts.
        Does not generate or persist schedules.
        """
        violations: list[ConstraintViolation] = []

        # Fetch working days & time slots
        wd_stmt = select(WorkingDay).where(
            WorkingDay.school_id == school_id,
            WorkingDay.academic_year_id == data.academic_year_id,
            WorkingDay.is_working == True,
            WorkingDay.is_deleted == False,
        )
        working_days = (await self.db.execute(wd_stmt)).scalars().all()

        ts_stmt = select(TimeSlot).where(
            TimeSlot.school_id == school_id,
            TimeSlot.academic_year_id == data.academic_year_id,
            TimeSlot.is_teaching == True,
            TimeSlot.is_break == False,
            TimeSlot.is_deleted == False,
        )
        time_slots = (await self.db.execute(ts_stmt)).scalars().all()

        if not working_days:
            violations.append(
                ConstraintViolation(
                    constraint_type="HARD",
                    rule_name="Working Days Config",
                    message="No active working days configured for the academic year.",
                )
            )

        if not time_slots:
            violations.append(
                ConstraintViolation(
                    constraint_type="HARD",
                    rule_name="Time Slots Config",
                    message="No active teaching time slots configured for the academic year.",
                )
            )

        # Fetch allocations & workloads
        alloc_stmt = select(TeacherSubjectAllocation).where(
            TeacherSubjectAllocation.school_id == school_id,
            TeacherSubjectAllocation.academic_year_id == data.academic_year_id,
            TeacherSubjectAllocation.term_id == data.term_id,
            TeacherSubjectAllocation.status == "ACTIVE",
            TeacherSubjectAllocation.is_deleted == False,
        )
        allocations = (await self.db.execute(alloc_stmt)).scalars().all()

        for al in allocations:
            # Check teacher workload config
            wl_stmt = select(TeacherWorkload).where(
                TeacherWorkload.teacher_id == al.teacher_id,
                TeacherWorkload.school_id == school_id,
                TeacherWorkload.is_deleted == False,
            )
            wl = (await self.db.execute(wl_stmt)).scalar_one_or_none()

            total_limit = al.weekly_period_limit or 5
            if wl and total_limit > wl.maximum_weekly_periods:
                violations.append(
                    ConstraintViolation(
                        constraint_type="HARD",
                        rule_name="Teacher Workload Capacity",
                        message=f"Teacher subject allocation ({total_limit} periods) exceeds maximum weekly capacity ({wl.maximum_weekly_periods}).",
                        entity_details={"teacher_id": str(al.teacher_id), "subject_id": str(al.subject_id)},
                    )
                )

        return ValidationResponse(is_valid=len(violations) == 0, violations=violations)
