"""
Service class orchestrating business actions and cache management for Timetable Dashboard KPIs.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.timetable_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.timetable_dashboard.repository import TimetableDashboardRepository
from app.modules.timetable_dashboard.schemas import TimetableKPIsResponse

logger = logging.getLogger(__name__)


class TimetableDashboardService:
    """
    Service class for Timetable Dashboard KPI retrieval.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TimetableDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_kpis(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        actor: User | None = None,
    ) -> TimetableKPIsResponse:
        cache_key = f"timetable_dashboard:kpis:{school_id}:{academic_year_id}:{term_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return TimetableKPIsResponse.model_validate(cached)

        # Retrieve core counters and statistics
        total = await self.repo.get_total_timetables(school_id, academic_year_id, term_id)
        published = await self.repo.get_published_timetables_count(school_id, academic_year_id, term_id)
        draft = await self.repo.get_draft_timetables_count(school_id, academic_year_id, term_id)
        classes = await self.repo.get_total_classes_scheduled(school_id, academic_year_id, term_id)
        teachers = await self.repo.get_total_teachers_scheduled(school_id, academic_year_id, term_id)
        rooms = await self.repo.get_total_rooms_utilized(school_id, academic_year_id, term_id)
        avg_workload = await self.repo.get_avg_teacher_workload(school_id)
        avg_utilization = await self.repo.get_avg_room_utilization(school_id, academic_year_id, term_id)
        weekly_periods = await self.repo.get_total_weekly_periods(school_id, academic_year_id, term_id)
        subs_today = await self.repo.get_substitutions_today(school_id)
        conflicts_resolved = await self.repo.get_conflicts_resolved_count(school_id)
        pending_conflicts = await self.repo.get_conflicts_pending_count(school_id)

        data = {
            "total_timetables": total,
            "published_timetables": published,
            "draft_timetables": draft,
            "total_classes_scheduled": classes,
            "total_teachers_scheduled": teachers,
            "total_rooms_utilized": rooms,
            "average_teacher_workload": avg_workload,
            "average_room_utilization": avg_utilization,
            "total_weekly_periods": weekly_periods,
            "substitutions_today": subs_today,
            "conflicts_resolved": conflicts_resolved,
            "pending_conflicts": pending_conflicts,
        }

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit Log Action
        if actor:
            await self.audit.log_action(
                module="timetable_dashboard",
                action="read_kpis",
                entity_name="TimetableDashboard",
                entity_id=school_id,
                user_id=actor.id,
                school_id=school_id,
            )

        return TimetableKPIsResponse.model_validate(data)

    async def invalidate_dashboard_cache(self, school_id: uuid.UUID) -> None:
        """Invalidates timetable dashboard, analytics, and reports cache."""
        pattern_keys = [
            f"timetable_dashboard:kpis:{school_id}:*",
            f"timetable_dashboard:analytics:{school_id}:*",
            f"timetable_dashboard:charts:{school_id}:*",
            f"timetable_dashboard:reports:*:{school_id}:*",
        ]
        for pattern in pattern_keys:
            try:
                await self.cache.delete_pattern(pattern)
            except Exception as e:
                logger.warning("Failed to invalidate pattern %s: %s", pattern, e)
