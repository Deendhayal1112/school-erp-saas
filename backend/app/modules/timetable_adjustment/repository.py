"""
Repository for Timetable Adjustments & Teacher Substitution.
Handles all database CRUD operations and filtering.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.timetable_adjustment.enums import (
    AdjustmentStatus,
    SubstitutionStatus,
)
from app.modules.timetable_adjustment.models import (
    AdjustmentHistory,
    SubstitutionHistory,
    TeacherSubstitution,
    TimetableAdjustment,
)
from app.modules.timetable_adjustment.schemas import (
    TimetableAdjustmentCreate,
    TeacherSubstitutionCreate,
    TimetableAdjustmentUpdate,
)


class TimetableAdjustmentRepository:
    """CRUD and query operations for TimetableAdjustment and AdjustmentHistory."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Adjustment CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        school_id: uuid.UUID,
        payload: TimetableAdjustmentCreate,
        old_teacher_id: uuid.UUID | None,
        old_room_id: uuid.UUID | None,
        old_time_slot_id: uuid.UUID | None,
        old_working_day_id: uuid.UUID | None,
        created_by: uuid.UUID,
    ) -> TimetableAdjustment:
        adjustment = TimetableAdjustment(
            school_id=school_id,
            class_timetable_entry_id=payload.class_timetable_entry_id,
            adjustment_type=payload.adjustment_type,
            reason=payload.reason,
            old_teacher_id=old_teacher_id,
            old_room_id=old_room_id,
            old_time_slot_id=old_time_slot_id,
            old_working_day_id=old_working_day_id,
            new_teacher_id=payload.new_teacher_id,
            new_room_id=payload.new_room_id,
            new_time_slot_id=payload.new_time_slot_id,
            new_working_day_id=payload.new_working_day_id,
            effective_date=payload.effective_date,
            expiry_date=payload.expiry_date,
            is_recurring=payload.is_recurring,
            status=AdjustmentStatus.PENDING,
            remarks=payload.remarks,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(adjustment)
        await self.db.flush()
        return adjustment

    async def get_by_id(
        self, adjustment_id: uuid.UUID, school_id: uuid.UUID
    ) -> TimetableAdjustment | None:
        stmt = select(TimetableAdjustment).where(
            TimetableAdjustment.id == adjustment_id,
            TimetableAdjustment.school_id == school_id,
            TimetableAdjustment.is_deleted == False,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        school_id: uuid.UUID,
        status: AdjustmentStatus | None = None,
        entry_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TimetableAdjustment], int]:
        stmt = select(TimetableAdjustment).where(
            TimetableAdjustment.school_id == school_id,
            TimetableAdjustment.is_deleted == False,
        )
        if status:
            stmt = stmt.where(TimetableAdjustment.status == status)
        if entry_id:
            stmt = stmt.where(TimetableAdjustment.class_timetable_entry_id == entry_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(TimetableAdjustment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        results = (await self.db.execute(stmt)).scalars().all()
        return list(results), total

    async def update(
        self,
        adjustment: TimetableAdjustment,
        payload: TimetableAdjustmentUpdate,
        updated_by: uuid.UUID,
    ) -> TimetableAdjustment:
        if payload.reason is not None:
            adjustment.reason = payload.reason
        if payload.new_teacher_id is not None:
            adjustment.new_teacher_id = payload.new_teacher_id
        if payload.new_room_id is not None:
            adjustment.new_room_id = payload.new_room_id
        if payload.new_time_slot_id is not None:
            adjustment.new_time_slot_id = payload.new_time_slot_id
        if payload.new_working_day_id is not None:
            adjustment.new_working_day_id = payload.new_working_day_id
        if payload.effective_date is not None:
            adjustment.effective_date = payload.effective_date
        if payload.expiry_date is not None:
            adjustment.expiry_date = payload.expiry_date
        if payload.is_recurring is not None:
            adjustment.is_recurring = payload.is_recurring
        if payload.remarks is not None:
            adjustment.remarks = payload.remarks
        adjustment.updated_by = updated_by
        self.db.add(adjustment)
        await self.db.flush()
        return adjustment

    async def soft_delete(
        self, adjustment: TimetableAdjustment, deleted_by: uuid.UUID
    ) -> None:
        adjustment.is_deleted = True
        adjustment.deleted_at = datetime.utcnow()
        adjustment.updated_by = deleted_by
        self.db.add(adjustment)
        await self.db.flush()

    async def update_status(
        self,
        adjustment: TimetableAdjustment,
        new_status: AdjustmentStatus,
        actor_id: uuid.UUID,
        approved_at: datetime | None = None,
    ) -> TimetableAdjustment:
        adjustment.status = new_status
        adjustment.updated_by = actor_id
        if approved_at:
            adjustment.approved_by = actor_id
            adjustment.approved_at = approved_at
        self.db.add(adjustment)
        await self.db.flush()
        return adjustment

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def add_history(
        self,
        school_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        from_status: str,
        to_status: str,
        action: str,
        actor_id: uuid.UUID | None,
        notes: str | None = None,
    ) -> AdjustmentHistory:
        history = AdjustmentHistory(
            school_id=school_id,
            adjustment_id=adjustment_id,
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_id=actor_id,
            notes=notes,
            changed_at=datetime.utcnow(),
        )
        self.db.add(history)
        await self.db.flush()
        return history

    async def get_history(
        self, adjustment_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[AdjustmentHistory]:
        stmt = select(AdjustmentHistory).where(
            AdjustmentHistory.adjustment_id == adjustment_id,
            AdjustmentHistory.school_id == school_id,
        ).order_by(AdjustmentHistory.changed_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def get_summary(self, school_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(
                TimetableAdjustment.status,
                func.count(TimetableAdjustment.id).label("cnt"),
            )
            .where(
                TimetableAdjustment.school_id == school_id,
                TimetableAdjustment.is_deleted == False,
            )
            .group_by(TimetableAdjustment.status)
        )
        rows = (await self.db.execute(stmt)).all()
        result: dict[str, int] = {s.value: 0 for s in AdjustmentStatus}
        for row in rows:
            result[row.status.value] = row.cnt
        return result


class TeacherSubstitutionRepository:
    """CRUD and query operations for TeacherSubstitution and SubstitutionHistory."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Substitution CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        school_id: uuid.UUID,
        payload: TeacherSubstitutionCreate,
    ) -> TeacherSubstitution:
        sub = TeacherSubstitution(
            school_id=school_id,
            original_teacher_id=payload.original_teacher_id,
            substitute_teacher_id=payload.substitute_teacher_id,
            class_id=payload.class_id,
            section_id=payload.section_id,
            subject_id=payload.subject_id,
            working_day_id=payload.working_day_id,
            time_slot_id=payload.time_slot_id,
            reason=payload.reason,
            substitution_type=payload.substitution_type,
            effective_date=payload.effective_date,
            status=SubstitutionStatus.PENDING,
            remarks=payload.remarks,
        )
        self.db.add(sub)
        await self.db.flush()
        return sub

    async def get_by_id(
        self, substitution_id: uuid.UUID, school_id: uuid.UUID
    ) -> TeacherSubstitution | None:
        stmt = select(TeacherSubstitution).where(
            TeacherSubstitution.id == substitution_id,
            TeacherSubstitution.school_id == school_id,
            TeacherSubstitution.is_deleted == False,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        school_id: uuid.UUID,
        status: SubstitutionStatus | None = None,
        original_teacher_id: uuid.UUID | None = None,
        substitute_teacher_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TeacherSubstitution], int]:
        stmt = select(TeacherSubstitution).where(
            TeacherSubstitution.school_id == school_id,
            TeacherSubstitution.is_deleted == False,
        )
        if status:
            stmt = stmt.where(TeacherSubstitution.status == status)
        if original_teacher_id:
            stmt = stmt.where(TeacherSubstitution.original_teacher_id == original_teacher_id)
        if substitute_teacher_id:
            stmt = stmt.where(TeacherSubstitution.substitute_teacher_id == substitute_teacher_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(TeacherSubstitution.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        results = (await self.db.execute(stmt)).scalars().all()
        return list(results), total

    async def update_status(
        self,
        substitution: TeacherSubstitution,
        new_status: SubstitutionStatus,
        actor_id: uuid.UUID,
        approved_at: datetime | None = None,
    ) -> TeacherSubstitution:
        substitution.status = new_status
        if approved_at:
            substitution.approved_by = actor_id
            substitution.approved_at = approved_at
        self.db.add(substitution)
        await self.db.flush()
        return substitution

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def add_history(
        self,
        school_id: uuid.UUID,
        substitution_id: uuid.UUID,
        from_status: str,
        to_status: str,
        action: str,
        actor_id: uuid.UUID | None,
        notes: str | None = None,
    ) -> SubstitutionHistory:
        history = SubstitutionHistory(
            school_id=school_id,
            substitution_id=substitution_id,
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_id=actor_id,
            notes=notes,
            changed_at=datetime.utcnow(),
        )
        self.db.add(history)
        await self.db.flush()
        return history

    async def get_history(
        self, substitution_id: uuid.UUID, school_id: uuid.UUID
    ) -> list[SubstitutionHistory]:
        stmt = select(SubstitutionHistory).where(
            SubstitutionHistory.substitution_id == substitution_id,
            SubstitutionHistory.school_id == school_id,
        ).order_by(SubstitutionHistory.changed_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())
