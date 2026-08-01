"""
Service class orchestrating business actions and cache management for Timetable Analytics and Charts.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.timetable_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.timetable_dashboard.repository import TimetableDashboardRepository
from app.modules.timetable_dashboard.schemas import (
    AnalyticsResponse,
    ChartItem,
    ChartsResponse,
    ClassPeriodCountItem,
    DailyHoursItem,
    HeatmapCell,
    MonthCountPair,
    NameCountPair,
    RoomUtilizationItem,
    SubjectDistributionItem,
    TeacherPeriodCountItem,
    TimetableUtilizationItem,
    WeeklyHoursItem,
)

logger = logging.getLogger(__name__)


class TimetableAnalyticsService:
    """
    Service class for Timetable Analytics and Charts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TimetableDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_analytics(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        actor: User | None = None,
    ) -> AnalyticsResponse:
        cache_key = f"timetable_dashboard:analytics:{school_id}:{academic_year_id}:{term_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AnalyticsResponse.model_validate(cached)

        # 1. Teacher workload distribution
        workload_dist = await self.repo.get_teacher_workload_distribution(school_id)
        # 2. Room utilization
        room_util = await self.repo.get_room_utilization_per_room(school_id, academic_year_id, term_id)
        # 3. Subject distribution
        subject_dist = await self.repo.get_subject_distribution(school_id, academic_year_id, term_id)
        # 4. Class-wise period count
        class_periods = await self.repo.get_class_wise_period_count(school_id, academic_year_id, term_id)
        # 5. Teacher-wise period count
        teacher_periods = await self.repo.get_teacher_wise_period_count(school_id, academic_year_id, term_id)
        # 6. Daily teaching hours
        daily_hours = await self.repo.get_daily_teaching_hours(school_id, academic_year_id, term_id)
        # 7. Weekly teaching hours
        weekly_hours = await self.repo.get_weekly_teaching_hours(school_id, academic_year_id, term_id)
        # 8. Timetable utilization
        timetable_util = await self.repo.get_timetable_utilization(school_id, academic_year_id)
        # 9. Substitution trends
        sub_trends = await self.repo.get_substitution_trends(school_id)
        # 10. Conflict trends
        conflict_trends = await self.repo.get_conflict_trends(school_id)

        data = {
            "teacher_workload_distribution": [
                NameCountPair(name=k, count=v) for k, v in workload_dist.items()
            ],
            "room_utilization": [
                RoomUtilizationItem(room_name=r[0], utilization_percentage=r[1])
                for r in room_util
            ],
            "subject_distribution": [
                SubjectDistributionItem(subject_name=s[0], period_count=s[1])
                for s in subject_dist
            ],
            "class_wise_period_count": [
                ClassPeriodCountItem(class_name=c[0], section_name=c[1], period_count=c[2])
                for c in class_periods
            ],
            "teacher_wise_period_count": [
                TeacherPeriodCountItem(teacher_name=f"{t[0]} {t[1]}", period_count=t[2])
                for t in teacher_periods
            ],
            "daily_teaching_hours": [
                DailyHoursItem(day_name=d[0].value if hasattr(d[0], "value") else str(d[0]), hours=float(d[1]))
                for d in daily_hours
            ],
            "weekly_teaching_hours": [
                WeeklyHoursItem(week_start=w[0], hours=float(w[1]))
                for w in weekly_hours
            ],
            "timetable_utilization": [
                TimetableUtilizationItem(
                    term_name=t[0],
                    published_count=t[1],
                    total_count=t[2],
                    utilization_percentage=round((t[1] / t[2]) * 100.0, 2) if t[2] > 0 else 0.0,
                )
                for t in timetable_util
            ],
            "substitution_trends": [
                MonthCountPair(month=st[0], count=st[1]) for st in sub_trends
            ],
            "conflict_trends": [
                MonthCountPair(month=ct[0], count=ct[1]) for ct in conflict_trends
            ],
        }

        response_obj = AnalyticsResponse.model_validate(data)
        await self.cache.set(
            cache_key, response_obj.model_dump(mode="json"), DASHBOARD_CACHE_TTL
        )

        if actor:
            await self.audit.log_action(
                module="timetable_dashboard",
                action="read_analytics",
                entity_name="TimetableDashboard",
                entity_id=school_id,
                user_id=actor.id,
                school_id=school_id,
            )

        return response_obj

    async def get_charts(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
        actor: User | None = None,
    ) -> ChartsResponse:
        cache_key = f"timetable_dashboard:charts:{school_id}:{academic_year_id}:{term_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ChartsResponse.model_validate(cached)

        analytics = await self.get_analytics(school_id, academic_year_id, term_id, actor)
        heatmap_data = await self.repo.get_weekly_timetable_heatmap(school_id, academic_year_id, term_id)

        # Build chart data structures from analytics
        data = {
            "weekly_timetable_heatmap": [
                HeatmapCell(day_name=h["day_name"], time_slot=h["time_slot"], count=h["count"])
                for h in heatmap_data
            ],
            "teacher_workload": [
                ChartItem(label=w.name, value=float(w.count))
                for w in analytics.teacher_workload_distribution
            ],
            "room_occupancy": [
                ChartItem(label=r.room_name, value=r.utilization_percentage)
                for r in analytics.room_utilization
            ],
            "subject_distribution": [
                ChartItem(label=s.subject_name, value=float(s.period_count))
                for s in analytics.subject_distribution
            ],
            "daily_schedule": [
                ChartItem(label=d.day_name, value=d.hours)
                for d in analytics.daily_teaching_hours
            ],
            "conflict_statistics": [
                ChartItem(label=c.month, value=float(c.count))
                for c in analytics.conflict_trends
            ],
            "substitution_statistics": [
                ChartItem(label=s.month, value=float(s.count))
                for s in analytics.substitution_trends
            ],
        }

        response_obj = ChartsResponse.model_validate(data)
        await self.cache.set(
            cache_key, response_obj.model_dump(mode="json"), DASHBOARD_CACHE_TTL
        )

        if actor:
            await self.audit.log_action(
                module="timetable_dashboard",
                action="read_charts",
                entity_name="TimetableDashboard",
                entity_id=school_id,
                user_id=actor.id,
                school_id=school_id,
            )

        return response_obj
