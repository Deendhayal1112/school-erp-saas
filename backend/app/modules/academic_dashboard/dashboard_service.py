import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.modules.academic_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.academic_dashboard.repository import AcademicDashboardRepository
from app.modules.academic_dashboard.schemas import (
    ChartsResponse,
    DashboardKPIsResponse,
)


class AcademicDashboardService:
    """
    Service class orchestrating business actions and cache management for Academic Dashboard KPIs and Charts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AcademicDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_kpis(
        self, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> DashboardKPIsResponse:
        cache_key = f"academic_dashboard:kpis:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return DashboardKPIsResponse.model_validate(cached)

        data = await self.repo.get_kpi_counts(school_id)
        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit Log
        await self.audit.log_action(
            module="academic_dashboard",
            action="read_kpis",
            entity_name="AcademicDashboard",
            entity_id=school_id,
            user_id=user_id,
            school_id=school_id,
        )

        return DashboardKPIsResponse.model_validate(data)

    async def get_charts(
        self, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> ChartsResponse:
        cache_key = f"academic_dashboard:charts:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ChartsResponse.model_validate(cached)

        monthly_admissions = await self.repo.get_monthly_admissions(school_id)
        curriculum_progress = await self.repo.get_curriculum_progress(school_id)
        class_distribution = await self.repo.get_class_distributions(school_id)
        academic_timeline = await self.repo.get_academic_timeline(school_id)

        data = {
            "monthly_admissions": monthly_admissions,
            "curriculum_progress": curriculum_progress,
            "class_distribution": class_distribution,
            "academic_timeline": academic_timeline,
        }

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit Log
        await self.audit.log_action(
            module="academic_dashboard",
            action="read_charts",
            entity_name="AcademicDashboard",
            entity_id=school_id,
            user_id=user_id,
            school_id=school_id,
        )

        return ChartsResponse.model_validate(data)

    async def invalidate_dashboard_cache(self, school_id: uuid.UUID) -> None:
        """Invalidates dashboard/analytics cache. Called when related modules update."""
        await self.cache.delete(f"academic_dashboard:kpis:{school_id}")
        await self.cache.delete(f"academic_dashboard:charts:{school_id}")
        await self.cache.delete(f"academic_dashboard:analytics:{school_id}")
