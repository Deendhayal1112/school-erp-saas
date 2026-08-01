import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.timetable_generator.enums import JobStatus
from app.modules.timetable_generator.models import (
    GenerationJob,
    GenerationLog,
    GenerationResult,
)


class TimetableGeneratorRepository:
    """
    Repository class executing optimized Async SQLAlchemy queries for timetable generation jobs,
    results, and log trails with tenant isolation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Job queries ---
    async def get_job(self, id: uuid.UUID, school_id: uuid.UUID) -> GenerationJob | None:
        stmt = select(GenerationJob).where(
            GenerationJob.id == id,
            GenerationJob.school_id == school_id,
            GenerationJob.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_job(self, job: GenerationJob) -> GenerationJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def list_jobs(
        self, school_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[GenerationJob]:
        stmt = (
            select(GenerationJob)
            .where(
                GenerationJob.school_id == school_id,
                GenerationJob.is_deleted == False,
            )
            .order_by(GenerationJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_active_running_job(
        self, school_id: uuid.UUID, term_id: uuid.UUID
    ) -> GenerationJob | None:
        stmt = select(GenerationJob).where(
            GenerationJob.school_id == school_id,
            GenerationJob.term_id == term_id,
            GenerationJob.status == JobStatus.RUNNING,
            GenerationJob.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- Result queries ---
    async def get_result(self, id: uuid.UUID, school_id: uuid.UUID) -> GenerationResult | None:
        stmt = select(GenerationResult).where(
            GenerationResult.id == id,
            GenerationResult.school_id == school_id,
            GenerationResult.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_result_by_job(
        self, job_id: uuid.UUID, school_id: uuid.UUID
    ) -> GenerationResult | None:
        stmt = select(GenerationResult).where(
            GenerationResult.generation_job_id == job_id,
            GenerationResult.school_id == school_id,
            GenerationResult.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- Log queries ---
    async def get_logs_by_job(
        self, job_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[GenerationLog]:
        stmt = (
            select(GenerationLog)
            .where(
                GenerationLog.generation_job_id == job_id,
                GenerationLog.school_id == school_id,
                GenerationLog.is_deleted == False,
            )
            .order_by(GenerationLog.timestamp.asc())
        )
        return (await self.session.execute(stmt)).scalars().all()
