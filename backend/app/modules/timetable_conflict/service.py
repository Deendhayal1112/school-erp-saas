import datetime
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.class_timetable.models import ClassTimetableEntry
from app.modules.timetable_conflict.conflict_engine import TimetableConflictEngine
from app.modules.timetable_conflict.enums import (
    ConflictSeverity,
    ConflictStatus,
)
from app.modules.timetable_conflict.exceptions import (
    ConflictAlreadyResolvedException,
    ConflictRecordNotFoundException,
    ResolutionFailedException,
)
from app.modules.timetable_conflict.models import (
    ConflictLog,
    ConflictRecord,
    ConflictResolution,
)
from app.modules.timetable_conflict.repository import TimetableConflictRepository
from app.modules.timetable_conflict.resolution_engine import TimetableResolutionEngine
from app.modules.timetable_conflict.schemas import (
    ConflictDetectRequest,
    ConflictDetectResponse,
    ConflictRecordResponse,
    ConflictReportResponse,
    ConflictReportSummary,
    ResolveConflictRequest,
    ResolveConflictResponse,
)
from app.modules.timetable_conflict.validators import validate_resolution_override

logger = logging.getLogger(__name__)


class TimetableConflictService:
    """
    Orchestration layer managing conflict detection scans, automatic/manual resolutions,
    retry loops, report caching, and operational audit trails.
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: TimetableConflictRepository | None = None,
        cache: CacheService | None = None,
        audit: AuditLogService | None = None,
    ) -> None:
        self.db = db
        self.repo = repo or TimetableConflictRepository(db)
        self.cache = cache or CacheService()
        self.audit = audit or AuditLogService(db)

    async def _clear_caches(self, school_id: uuid.UUID) -> None:
        await self.cache.delete_pattern(f"conflict_report:{school_id}:*")
        await self.cache.delete_pattern(f"class_timetable:weekly:{school_id}:*")
        await self.cache.delete_pattern(f"teacher_timetable:weekly:{school_id}:*")

    async def detect_and_record_conflicts(
        self, school_id: uuid.UUID, data: ConflictDetectRequest, actor: User
    ) -> ConflictDetectResponse:
        """
        Runs the Conflict Engine scan and persists non-duplicate rule violations in the database.
        """
        engine = TimetableConflictEngine(self.db)
        detected_list = await engine.detect_conflicts(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            section_id=data.section_id,
        )

        critical_count = 0
        warning_count = 0
        recorded_count = 0

        for cd in detected_list:
            if cd["severity"] == ConflictSeverity.CRITICAL:
                critical_count += 1
            else:
                warning_count += 1

            # Check if this exact conflict is already logged in PENDING state
            existing = await self.repo.get_existing_pending_conflict(
                school_id=school_id,
                conflict_type=cd["conflict_type"],
                working_day_id=cd["working_day_id"],
                time_slot_id=cd["time_slot_id"],
                teacher_id=cd["teacher_id"],
                class_id=cd["class_id"],
                section_id=cd["section_id"],
            )

            if not existing:
                # Save new conflict record
                record = ConflictRecord(
                    school_id=school_id,
                    conflict_type=cd["conflict_type"],
                    severity=cd["severity"],
                    class_id=cd["class_id"],
                    section_id=cd["section_id"],
                    teacher_id=cd["teacher_id"],
                    room_id=cd["room_id"],
                    subject_id=cd["subject_id"],
                    working_day_id=cd["working_day_id"],
                    time_slot_id=cd["time_slot_id"],
                    description=cd["description"],
                    status=ConflictStatus.PENDING,
                )
                await self.repo.save_conflict(record)

                # Save execution log
                clog = ConflictLog(
                    school_id=school_id,
                    conflict_record_id=record.id,
                    action="DETECTION",
                    message=f"Conflict detected and logged: {cd['description']}",
                )
                self.db.add(clog)
                recorded_count += 1

        if recorded_count > 0:
            await self.db.commit()
            await self._clear_caches(school_id)

            # Audit event
            await self.audit.log_action(
                module="timetable_conflict",
                action="conflict.detected",
                entity_name="ConflictRecord",
                entity_id=None,
                user_id=actor.id,
                school_id=school_id,
            )
            await self.db.commit()

        return ConflictDetectResponse(
            total_detected=len(detected_list),
            critical_count=critical_count,
            warning_count=warning_count,
            message=f"Conflict detection scan complete. Recorded {recorded_count} new conflict records.",
        )

    async def get_conflict(self, id: uuid.UUID, school_id: uuid.UUID) -> ConflictRecord:
        record = await self.repo.get_conflict(id, school_id)
        if not record:
            raise ConflictRecordNotFoundException()
        return record

    async def resolve_conflict(
        self, conflict_id: uuid.UUID, school_id: uuid.UUID, data: ResolveConflictRequest, actor: User
    ) -> ResolveConflictResponse:
        """
        Resolves conflict using automatic suggestions or applying manual override swaps.
        """
        conflict = await self.get_conflict(conflict_id, school_id)
        if conflict.status == ConflictStatus.RESOLVED:
            raise ConflictAlreadyResolvedException()

        resolution_engine = TimetableResolutionEngine(self.db)

        if data.resolution_strategy == "AUTOMATIC":
            res = await resolution_engine.resolve_automatically(conflict, actor.id)
            action_taken = res.action_taken
        else:
            validate_resolution_override(data.resolution_strategy, data.action_taken)

            # Apply manual resolution reallocations
            entry_stmt = select(ClassTimetableEntry).where(
                ClassTimetableEntry.school_id == school_id,
                ClassTimetableEntry.working_day_id == conflict.working_day_id,
                ClassTimetableEntry.time_slot_id == conflict.time_slot_id,
                ClassTimetableEntry.teacher_id == conflict.teacher_id,
                ClassTimetableEntry.subject_id == conflict.subject_id,
                ClassTimetableEntry.is_deleted == False,
            )
            entry = (await self.db.execute(entry_stmt)).scalars().first()
            if not entry:
                raise ResolutionFailedException("Conflicting timetable entry not found.")

            if data.alternative_room_id:
                entry.room_id = data.alternative_room_id
            if data.alternative_teacher_id:
                entry.teacher_id = data.alternative_teacher_id
            if data.alternative_working_day_id and data.alternative_time_slot_id:
                entry.working_day_id = data.alternative_working_day_id
                entry.time_slot_id = data.alternative_time_slot_id

            self.db.add(entry)

            # Mark resolved
            conflict.status = ConflictStatus.RESOLVED
            conflict.resolved_at = datetime.datetime.utcnow()
            conflict.resolved_by = actor.id
            conflict.remarks = f"Resolved manually: {data.action_taken}"
            self.db.add(conflict)

            # Record resolution mapping
            res = ConflictResolution(
                school_id=school_id,
                conflict_record_id=conflict.id,
                resolution_strategy=data.resolution_strategy,
                action_taken=data.action_taken,
                resolved_by=actor.id,
                resolved_at=datetime.datetime.utcnow(),
                status="SUCCESS",
            )
            self.db.add(res)
            action_taken = data.action_taken

        # Log resolution try
        clog = ConflictLog(
            school_id=school_id,
            conflict_record_id=conflict.id,
            action="RESOLUTION_TRY",
            message=f"Conflict resolved successfully via {data.resolution_strategy}. Action: {action_taken}",
        )
        self.db.add(clog)

        await self.db.commit()
        await self._clear_caches(school_id)

        # Log Audit
        await self.audit.log_action(
            module="timetable_conflict",
            action="conflict.resolved",
            entity_name="ConflictRecord",
            entity_id=conflict.id,
            user_id=actor.id,
            school_id=school_id,
        )
        await self.db.commit()

        return ResolveConflictResponse(
            status="SUCCESS",
            message="Timetable conflict resolved successfully.",
        )

    async def retry_resolution(
        self, conflict_id: uuid.UUID, school_id: uuid.UUID, actor: User
    ) -> ResolveConflictResponse:
        """
        Re-triggers resolution strategy search. Proposes suggestions if auto resolution is blocked.
        """
        conflict = await self.get_conflict(conflict_id, school_id)
        if conflict.status == ConflictStatus.RESOLVED:
            raise ConflictAlreadyResolvedException()

        resolution_engine = TimetableResolutionEngine(self.db)
        suggestions = await resolution_engine.suggest_alternatives(conflict)

        # Log Retry action
        clog = ConflictLog(
            school_id=school_id,
            conflict_record_id=conflict.id,
            action="RESOLUTION_TRY",
            message="Resolution retry triggered. Search computed alternative suggestion paths.",
        )
        self.db.add(clog)
        await self.db.commit()

        # Log Audit
        await self.audit.log_action(
            module="timetable_conflict",
            action="conflict.retry_executed",
            entity_name="ConflictRecord",
            entity_id=conflict.id,
            user_id=actor.id,
            school_id=school_id,
        )
        await self.db.commit()

        return ResolveConflictResponse(
            status="PENDING",
            message="Auto resolution failed or blocked. Review alternative suggestions to apply.",
            suggestions=suggestions,
        )

    async def get_conflict_report(
        self, school_id: uuid.UUID, academic_year_id: uuid.UUID, term_id: uuid.UUID
    ) -> ConflictReportResponse:
        """
        Generates/fetches a cached summary report of all conflict metrics.
        """
        cache_key = f"conflict_report:{school_id}:{academic_year_id}:{term_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Pydantic v2 validation of cached dict
            return ConflictReportResponse.model_validate(cached)

        # Compute summary metrics
        summary_dict = await self.repo.get_school_conflict_summary(school_id)
        summary = ConflictReportSummary(
            total_conflicts=summary_dict["total"],
            pending_count=summary_dict["pending"],
            resolved_count=summary_dict["resolved"],
            critical_count=summary_dict["critical"],
            warning_count=summary_dict["warning"],
        )

        # Retrieve conflicts
        conflicts = await self.repo.list_conflicts(
            school_id=school_id,
            class_id=None,  # list all
        )
        conf_responses = [ConflictRecordResponse.model_validate(c) for c in conflicts]

        report = ConflictReportResponse(
            summary=summary,
            conflicts=conf_responses,
            generated_at=datetime.datetime.utcnow(),
        )

        # Save cache
        await self.cache.set(cache_key, report.model_dump(mode="json"), ttl=300)
        return report
