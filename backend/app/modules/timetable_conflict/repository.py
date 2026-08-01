import uuid
from collections.abc import Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.timetable_conflict.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
)
from app.modules.timetable_conflict.models import (
    ConflictLog,
    ConflictRecord,
    ConflictResolution,
)


class TimetableConflictRepository:
    """
    Repository class performing tenant-isolated Database operations for conflict tracking,
    summary indicators, logs, and query filtering.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_conflict(self, id: uuid.UUID, school_id: uuid.UUID) -> ConflictRecord | None:
        stmt = (
            select(ConflictRecord)
            .options(
                joinedload(ConflictRecord.school_class),
                joinedload(ConflictRecord.section),
                joinedload(ConflictRecord.teacher).joinedload(Teacher.employee),
                joinedload(ConflictRecord.room),
                joinedload(ConflictRecord.subject),
                joinedload(ConflictRecord.working_day),
                joinedload(ConflictRecord.time_slot),
            )
            .where(
                ConflictRecord.id == id,
                ConflictRecord.school_id == school_id,
                ConflictRecord.is_deleted == False,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        self.session.add(conflict)
        await self.session.flush()
        return conflict

    async def get_existing_pending_conflict(
        self,
        school_id: uuid.UUID,
        conflict_type: ConflictType,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        teacher_id: uuid.UUID,
        class_id: uuid.UUID,
        section_id: uuid.UUID,
    ) -> ConflictRecord | None:
        """Finds if an identical conflict is already recorded in PENDING state to avoid duplicates."""
        stmt = select(ConflictRecord).where(
            ConflictRecord.school_id == school_id,
            ConflictRecord.conflict_type == conflict_type,
            ConflictRecord.working_day_id == working_day_id,
            ConflictRecord.time_slot_id == time_slot_id,
            ConflictRecord.teacher_id == teacher_id,
            ConflictRecord.class_id == class_id,
            ConflictRecord.section_id == section_id,
            ConflictRecord.status == ConflictStatus.PENDING,
            ConflictRecord.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_conflicts(
        self,
        school_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        conflict_type: ConflictType | None = None,
        severity: ConflictSeverity | None = None,
        teacher_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        status: ConflictStatus | None = None,
        sort_by: str = "detected_at",
        sort_order: str = "desc",
    ) -> Sequence[ConflictRecord]:
        """
        Retrieves a filtered, sorted, and paginated list of conflict records.
        """
        stmt = select(ConflictRecord).where(
            ConflictRecord.school_id == school_id,
            ConflictRecord.is_deleted == False,
        )

        # Filters
        if conflict_type:
            stmt = stmt.where(ConflictRecord.conflict_type == conflict_type)
        if severity:
            stmt = stmt.where(ConflictRecord.severity == severity)
        if teacher_id:
            stmt = stmt.where(ConflictRecord.teacher_id == teacher_id)
        if room_id:
            stmt = stmt.where(ConflictRecord.room_id == room_id)
        if class_id:
            stmt = stmt.where(ConflictRecord.class_id == class_id)
        if section_id:
            stmt = stmt.where(ConflictRecord.section_id == section_id)
        if status:
            stmt = stmt.where(ConflictRecord.status == status)

        # Sorting
        order_col = ConflictRecord.detected_at
        if sort_by == "severity":
            order_col = ConflictRecord.severity  # type: ignore

        if sort_order == "desc":
            stmt = stmt.order_by(desc(order_col))
        else:
            stmt = stmt.order_by(order_col)

        stmt = stmt.offset(skip).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_resolutions_by_conflict(
        self, conflict_record_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[ConflictResolution]:
        stmt = select(ConflictResolution).where(
            ConflictResolution.conflict_record_id == conflict_record_id,
            ConflictResolution.school_id == school_id,
            ConflictResolution.is_deleted == False,
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_logs_by_conflict(
        self, conflict_record_id: uuid.UUID, school_id: uuid.UUID
    ) -> Sequence[ConflictLog]:
        stmt = select(ConflictLog).where(
            ConflictLog.conflict_record_id == conflict_record_id,
            ConflictLog.school_id == school_id,
            ConflictLog.is_deleted == False,
        ).order_by(ConflictLog.timestamp.asc())
        return (await self.session.execute(stmt)).scalars().all()

    async def get_school_conflict_summary(self, school_id: uuid.UUID) -> dict[str, int]:
        """Computes summary statistics for a school's conflict history."""
        stmt = (
            select(
                func.count(ConflictRecord.id),
                func.sum(sa_case((ConflictRecord.status == ConflictStatus.PENDING, 1), else_=0)),
                func.sum(sa_case((ConflictRecord.status == ConflictStatus.RESOLVED, 1), else_=0)),
                func.sum(sa_case((ConflictRecord.severity == ConflictSeverity.CRITICAL, 1), else_=0)),
                func.sum(sa_case((ConflictRecord.severity == ConflictSeverity.WARNING, 1), else_=0)),
            )
            .where(
                ConflictRecord.school_id == school_id,
                ConflictRecord.is_deleted == False,
            )
        )
        res = (await self.session.execute(stmt)).first()
        if not res:
            return {"total": 0, "pending": 0, "resolved": 0, "critical": 0, "warning": 0}

        return {
            "total": res[0] or 0,
            "pending": int(res[1] or 0),
            "resolved": int(res[2] or 0),
            "critical": int(res[3] or 0),
            "warning": int(res[4] or 0),
        }


from sqlalchemy import case as sa_case

from app.modules.teacher.models import Teacher
