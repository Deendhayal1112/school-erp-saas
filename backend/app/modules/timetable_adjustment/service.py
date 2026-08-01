"""
Service layer for Timetable Adjustments & Teacher Substitution.
Orchestrates validation, engine logic, repository operations, audit logging,
and notifications.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.modules.class_timetable.models import ClassTimetableEntry
from app.modules.timetable_adjustment.adjustment_engine import AdjustmentEngine
from app.modules.timetable_adjustment.enums import (
    AdjustmentStatus,
    SubstitutionStatus,
)
from app.modules.timetable_adjustment.exceptions import (
    AdjustmentAlreadyProcessedException,
    AdjustmentNotFoundException,
    RollbackNotAllowedException,
    SubstitutionAlreadyProcessedException,
    SubstitutionNotFoundException,
)
from app.modules.timetable_adjustment.repository import (
    TeacherSubstitutionRepository,
    TimetableAdjustmentRepository,
)
from app.modules.timetable_adjustment.schemas import (
    AdjustmentSummaryResponse,
    SubstitutionSuggestionsResponse,
    TeacherSubstitutionCreate,
    TeacherSubstitutionResponse,
    TimetableAdjustmentCreate,
    TimetableAdjustmentResponse,
    TimetableAdjustmentUpdate,
)
from app.modules.timetable_adjustment.substitution_engine import SubstitutionEngine
from app.modules.timetable_adjustment.validators import (
    validate_effective_date,
    validate_expiry_date,
    validate_teacher_available_at_slot,
    validate_teacher_exists,
    validate_teacher_qualified,
    validate_timetable_entry_exists,
)

logger = logging.getLogger(__name__)

_IMMUTABLE_STATUSES = {
    AdjustmentStatus.APPROVED,
    AdjustmentStatus.APPLIED,
    AdjustmentStatus.REJECTED,
    AdjustmentStatus.ROLLED_BACK,
    AdjustmentStatus.EXPIRED,
}

_SUBSTITUTION_IMMUTABLE_STATUSES = {
    SubstitutionStatus.APPROVED,
    SubstitutionStatus.ACTIVE,
    SubstitutionStatus.COMPLETED,
    SubstitutionStatus.CANCELLED,
    SubstitutionStatus.REJECTED,
}


class TimetableAdjustmentService:
    """
    Orchestrates the full lifecycle of timetable adjustments.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TimetableAdjustmentRepository(db)
        self.engine = AdjustmentEngine(db)
        self.audit = AuditLogService(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_adjustment(
        self,
        school_id: uuid.UUID,
        payload: TimetableAdjustmentCreate,
        created_by: uuid.UUID,
    ) -> TimetableAdjustmentResponse:
        validate_effective_date(payload.effective_date)
        validate_expiry_date(payload.effective_date, payload.expiry_date)

        # Validate target entry exists
        entry = await validate_timetable_entry_exists(self.db, payload.class_timetable_entry_id, school_id)

        # Snapshot current values
        old_teacher_id = entry.teacher_id
        old_room_id = entry.room_id
        old_time_slot_id = entry.time_slot_id
        old_working_day_id = entry.working_day_id

        # Validate new resource availability
        if payload.new_teacher_id:
            await validate_teacher_exists(self.db, payload.new_teacher_id, school_id)
            await validate_teacher_available_at_slot(
                self.db,
                payload.new_teacher_id,
                payload.new_working_day_id or entry.working_day_id,
                payload.new_time_slot_id or entry.time_slot_id,
                school_id,
                exclude_entry_id=entry.id,
            )

        adjustment = await self.repo.create(
            school_id=school_id,
            payload=payload,
            old_teacher_id=old_teacher_id,
            old_room_id=old_room_id,
            old_time_slot_id=old_time_slot_id,
            old_working_day_id=old_working_day_id,
            created_by=created_by,
        )

        # Validate through the engine (conflict check)
        await self.engine.validate_adjustment(adjustment, entry)

        await self.repo.add_history(
            school_id=school_id,
            adjustment_id=adjustment.id,
            from_status="NONE",
            to_status=AdjustmentStatus.PENDING.value,
            action="CREATED",
            actor_id=created_by,
        )
        await self.audit.log_action(
            module="timetable_adjustment",
            action="CREATE",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=created_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(adjustment)
        return TimetableAdjustmentResponse.model_validate(adjustment)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_adjustment(
        self, school_id: uuid.UUID, adjustment_id: uuid.UUID
    ) -> TimetableAdjustmentResponse:
        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        return TimetableAdjustmentResponse.model_validate(adjustment)

    async def list_adjustments(
        self,
        school_id: uuid.UUID,
        status: AdjustmentStatus | None = None,
        entry_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TimetableAdjustmentResponse], int]:
        adjustments, total = await self.repo.list(
            school_id=school_id,
            status=status,
            entry_id=entry_id,
            page=page,
            page_size=page_size,
        )
        return [TimetableAdjustmentResponse.model_validate(a) for a in adjustments], total

    async def get_summary(
        self, school_id: uuid.UUID
    ) -> AdjustmentSummaryResponse:
        counts = await self.repo.get_summary(school_id)
        total = sum(counts.values())
        return AdjustmentSummaryResponse(
            total=total,
            pending=counts.get("PENDING", 0),
            approved=counts.get("APPROVED", 0),
            applied=counts.get("APPLIED", 0),
            rejected=counts.get("REJECTED", 0),
            rolled_back=counts.get("ROLLED_BACK", 0),
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_adjustment(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        payload: TimetableAdjustmentUpdate,
        updated_by: uuid.UUID,
    ) -> TimetableAdjustmentResponse:
        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        if adjustment.status != AdjustmentStatus.PENDING:
            raise AdjustmentAlreadyProcessedException(
                "Only PENDING adjustments can be updated."
            )
        if payload.effective_date:
            validate_effective_date(payload.effective_date)
        if payload.expiry_date and payload.effective_date:
            validate_expiry_date(payload.effective_date, payload.expiry_date)

        adjustment = await self.repo.update(adjustment, payload, updated_by)
        await self.audit.log_action(
            module="timetable_adjustment",
            action="UPDATE",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=updated_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(adjustment)
        return TimetableAdjustmentResponse.model_validate(adjustment)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_adjustment(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        deleted_by: uuid.UUID,
    ) -> None:
        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        if adjustment.status != AdjustmentStatus.PENDING:
            raise AdjustmentAlreadyProcessedException(
                "Only PENDING adjustments can be deleted."
            )
        await self.repo.soft_delete(adjustment, deleted_by)
        await self.audit.log_action(
            module="timetable_adjustment",
            action="DELETE",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=deleted_by,
            school_id=school_id,
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Approve
    # ------------------------------------------------------------------

    async def approve_adjustment(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        approved_by: uuid.UUID,
        remarks: str | None = None,
    ) -> TimetableAdjustmentResponse:
        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        if adjustment.status != AdjustmentStatus.PENDING:
            raise AdjustmentAlreadyProcessedException()

        prev_status = adjustment.status.value
        adjustment = await self.repo.update_status(
            adjustment,
            AdjustmentStatus.APPROVED,
            approved_by,
            approved_at=datetime.utcnow(),
        )
        if remarks:
            adjustment.remarks = remarks
            self.db.add(adjustment)

        await self.repo.add_history(
            school_id=school_id,
            adjustment_id=adjustment.id,
            from_status=prev_status,
            to_status=AdjustmentStatus.APPROVED.value,
            action="APPROVED",
            actor_id=approved_by,
            notes=remarks,
        )
        await self.audit.log_action(
            module="timetable_adjustment",
            action="APPROVE",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=approved_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(adjustment)
        return TimetableAdjustmentResponse.model_validate(adjustment)

    # ------------------------------------------------------------------
    # Reject
    # ------------------------------------------------------------------

    async def reject_adjustment(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        rejected_by: uuid.UUID,
        remarks: str,
    ) -> TimetableAdjustmentResponse:
        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        if adjustment.status != AdjustmentStatus.PENDING:
            raise AdjustmentAlreadyProcessedException()

        prev_status = adjustment.status.value
        adjustment = await self.repo.update_status(
            adjustment,
            AdjustmentStatus.REJECTED,
            rejected_by,
        )
        adjustment.remarks = remarks
        self.db.add(adjustment)

        await self.repo.add_history(
            school_id=school_id,
            adjustment_id=adjustment.id,
            from_status=prev_status,
            to_status=AdjustmentStatus.REJECTED.value,
            action="REJECTED",
            actor_id=rejected_by,
            notes=remarks,
        )
        await self.audit.log_action(
            module="timetable_adjustment",
            action="REJECT",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=rejected_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(adjustment)
        return TimetableAdjustmentResponse.model_validate(adjustment)

    # ------------------------------------------------------------------
    # Apply (apply APPROVED adjustment to live entry)
    # ------------------------------------------------------------------

    async def apply_adjustment(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        applied_by: uuid.UUID,
    ) -> TimetableAdjustmentResponse:
        from sqlalchemy import select as sa_select
        from app.modules.class_timetable.models import ClassTimetableEntry as CTE

        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        if adjustment.status != AdjustmentStatus.APPROVED:
            raise AdjustmentAlreadyProcessedException(
                "Only APPROVED adjustments can be applied."
            )

        # Fetch live entry
        stmt = sa_select(CTE).where(CTE.id == adjustment.class_timetable_entry_id)
        entry = (await self.db.execute(stmt)).scalar_one_or_none()
        if not entry:
            raise AdjustmentNotFoundException("Referenced timetable entry not found.")

        # Final conflict validation before apply
        await self.engine.validate_adjustment(adjustment, entry)
        await self.engine.apply_adjustment(adjustment, entry)

        prev_status = adjustment.status.value
        adjustment = await self.repo.update_status(
            adjustment, AdjustmentStatus.APPLIED, applied_by
        )
        await self.repo.add_history(
            school_id=school_id,
            adjustment_id=adjustment.id,
            from_status=prev_status,
            to_status=AdjustmentStatus.APPLIED.value,
            action="APPLIED",
            actor_id=applied_by,
        )
        await self.audit.log_action(
            module="timetable_adjustment",
            action="APPLY",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=applied_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(adjustment)
        return TimetableAdjustmentResponse.model_validate(adjustment)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def rollback_adjustment(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        rolled_back_by: uuid.UUID,
        notes: str | None = None,
    ) -> TimetableAdjustmentResponse:
        from sqlalchemy import select as sa_select
        from app.modules.class_timetable.models import ClassTimetableEntry as CTE

        adjustment = await self.repo.get_by_id(adjustment_id, school_id)
        if not adjustment:
            raise AdjustmentNotFoundException()
        if adjustment.status != AdjustmentStatus.APPLIED:
            raise RollbackNotAllowedException()

        stmt = sa_select(CTE).where(CTE.id == adjustment.class_timetable_entry_id)
        entry = (await self.db.execute(stmt)).scalar_one_or_none()
        if entry:
            await self.engine.rollback_adjustment(adjustment, entry)

        prev_status = adjustment.status.value
        adjustment = await self.repo.update_status(
            adjustment, AdjustmentStatus.ROLLED_BACK, rolled_back_by
        )
        await self.repo.add_history(
            school_id=school_id,
            adjustment_id=adjustment.id,
            from_status=prev_status,
            to_status=AdjustmentStatus.ROLLED_BACK.value,
            action="ROLLED_BACK",
            actor_id=rolled_back_by,
            notes=notes,
        )
        await self.audit.log_action(
            module="timetable_adjustment",
            action="ROLLBACK",
            entity_name="TimetableAdjustment",
            entity_id=adjustment.id,
            user_id=rolled_back_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(adjustment)
        return TimetableAdjustmentResponse.model_validate(adjustment)


class TeacherSubstitutionService:
    """
    Orchestrates the full lifecycle of teacher substitutions.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TeacherSubstitutionRepository(db)
        self.engine = SubstitutionEngine(db)
        self.audit = AuditLogService(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_substitution(
        self,
        school_id: uuid.UUID,
        payload: TeacherSubstitutionCreate,
        created_by: uuid.UUID,
    ) -> TeacherSubstitutionResponse:
        validate_effective_date(payload.effective_date)

        # Validate both teachers exist
        await validate_teacher_exists(self.db, payload.original_teacher_id, school_id)
        await validate_teacher_exists(self.db, payload.substitute_teacher_id, school_id)

        # Check substitute is qualified
        await validate_teacher_qualified(
            self.db,
            payload.substitute_teacher_id,
            payload.subject_id,
            school_id,
        )

        # Check substitute is available at this slot
        await validate_teacher_available_at_slot(
            self.db,
            payload.substitute_teacher_id,
            payload.working_day_id,
            payload.time_slot_id,
            school_id,
        )

        sub = await self.repo.create(school_id, payload)
        await self.repo.add_history(
            school_id=school_id,
            substitution_id=sub.id,
            from_status="NONE",
            to_status=SubstitutionStatus.PENDING.value,
            action="CREATED",
            actor_id=created_by,
        )
        await self.audit.log_action(
            module="teacher_substitution",
            action="CREATE",
            entity_name="TeacherSubstitution",
            entity_id=sub.id,
            user_id=created_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(sub)
        return TeacherSubstitutionResponse.model_validate(sub)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_substitution(
        self, school_id: uuid.UUID, substitution_id: uuid.UUID
    ) -> TeacherSubstitutionResponse:
        sub = await self.repo.get_by_id(substitution_id, school_id)
        if not sub:
            raise SubstitutionNotFoundException()
        return TeacherSubstitutionResponse.model_validate(sub)

    async def list_substitutions(
        self,
        school_id: uuid.UUID,
        status: SubstitutionStatus | None = None,
        original_teacher_id: uuid.UUID | None = None,
        substitute_teacher_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TeacherSubstitutionResponse], int]:
        subs, total = await self.repo.list(
            school_id=school_id,
            status=status,
            original_teacher_id=original_teacher_id,
            substitute_teacher_id=substitute_teacher_id,
            page=page,
            page_size=page_size,
        )
        return [TeacherSubstitutionResponse.model_validate(s) for s in subs], total

    # ------------------------------------------------------------------
    # Approve
    # ------------------------------------------------------------------

    async def approve_substitution(
        self,
        school_id: uuid.UUID,
        substitution_id: uuid.UUID,
        approved_by: uuid.UUID,
        remarks: str | None = None,
    ) -> TeacherSubstitutionResponse:
        sub = await self.repo.get_by_id(substitution_id, school_id)
        if not sub:
            raise SubstitutionNotFoundException()
        if sub.status != SubstitutionStatus.PENDING:
            raise SubstitutionAlreadyProcessedException()

        prev = sub.status.value
        sub = await self.repo.update_status(
            sub, SubstitutionStatus.APPROVED, approved_by, approved_at=datetime.utcnow()
        )
        if remarks:
            sub.remarks = remarks
            self.db.add(sub)

        await self.repo.add_history(
            school_id=school_id,
            substitution_id=sub.id,
            from_status=prev,
            to_status=SubstitutionStatus.APPROVED.value,
            action="APPROVED",
            actor_id=approved_by,
            notes=remarks,
        )
        await self.audit.log_action(
            module="teacher_substitution",
            action="APPROVE",
            entity_name="TeacherSubstitution",
            entity_id=sub.id,
            user_id=approved_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(sub)
        return TeacherSubstitutionResponse.model_validate(sub)

    # ------------------------------------------------------------------
    # Reject
    # ------------------------------------------------------------------

    async def reject_substitution(
        self,
        school_id: uuid.UUID,
        substitution_id: uuid.UUID,
        rejected_by: uuid.UUID,
        remarks: str,
    ) -> TeacherSubstitutionResponse:
        sub = await self.repo.get_by_id(substitution_id, school_id)
        if not sub:
            raise SubstitutionNotFoundException()
        if sub.status != SubstitutionStatus.PENDING:
            raise SubstitutionAlreadyProcessedException()

        prev = sub.status.value
        sub = await self.repo.update_status(
            sub, SubstitutionStatus.REJECTED, rejected_by
        )
        sub.remarks = remarks
        self.db.add(sub)

        await self.repo.add_history(
            school_id=school_id,
            substitution_id=sub.id,
            from_status=prev,
            to_status=SubstitutionStatus.REJECTED.value,
            action="REJECTED",
            actor_id=rejected_by,
            notes=remarks,
        )
        await self.audit.log_action(
            module="teacher_substitution",
            action="REJECT",
            entity_name="TeacherSubstitution",
            entity_id=sub.id,
            user_id=rejected_by,
            school_id=school_id,
        )
        await self.db.commit()
        await self.db.refresh(sub)
        return TeacherSubstitutionResponse.model_validate(sub)

    # ------------------------------------------------------------------
    # Suggestions
    # ------------------------------------------------------------------

    async def get_substitute_suggestions(
        self,
        school_id: uuid.UUID,
        subject_id: uuid.UUID,
        working_day_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        original_teacher_id: uuid.UUID,
    ) -> SubstitutionSuggestionsResponse:
        suggestions = await self.engine.suggest_substitutes(
            school_id=school_id,
            subject_id=subject_id,
            working_day_id=working_day_id,
            time_slot_id=time_slot_id,
            original_teacher_id=original_teacher_id,
        )
        return SubstitutionSuggestionsResponse(
            suggestions=suggestions,
            total_found=len(suggestions),
            message=f"{len(suggestions)} substitute(s) found." if suggestions else "No available substitutes found.",
        )
