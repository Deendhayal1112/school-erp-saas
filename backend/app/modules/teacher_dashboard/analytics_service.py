import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.teacher_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.teacher_dashboard.repository import TeacherDashboardRepository
from app.modules.teacher_dashboard.schemas import (
    AnalyticsResponse,
    ChartItem,
    ChartsResponse,
    DatePercentPair,
    MonthCountPair,
    NameCountPair,
)

logger = logging.getLogger(__name__)


class TeacherAnalyticsService:
    """
    Service class orchestrating business actions and cache management for Teacher Analytics and Charts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TeacherDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_analytics(
        self, school_id: uuid.UUID, actor: User
    ) -> AnalyticsResponse:
        cache_key = f"teacher_dashboard:analytics:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AnalyticsResponse.model_validate(cached)

        # 1. Department distributions
        dept_emps = await self.repo.get_department_wise_employees(school_id)
        dept_teachers = await self.repo.get_department_wise_teachers(school_id)

        # 2. Gender ratio
        gender_data = await self.repo.get_gender_distribution(school_id)

        # 3. Age groups
        ages = await self.repo.get_ages(school_id)
        today = date.today()
        age_buckets = {"<30": 0, "30-40": 0, "40-50": 0, "50+": 0}
        for dob in ages:
            age = (today - dob).days / 365.25
            if age < 30:
                age_buckets["<30"] += 1
            elif age < 40:
                age_buckets["30-40"] += 1
            elif age < 50:
                age_buckets["40-50"] += 1
            else:
                age_buckets["50+"] += 1

        # 4. Qualifications
        quals = await self.repo.get_highest_qualifications(school_id)
        qual_counts = {}
        for q in quals:
            qual_counts[q.value] = qual_counts.get(q.value, 0) + 1

        # 5. Experience buckets
        exp_comps = await self.repo.get_average_experience_components(school_id)
        exp_buckets = {"<2 Years": 0, "2-5 Years": 0, "5-10 Years": 0, "10+ Years": 0}
        for joining_date, prior in exp_comps:
            total_exp = ((today - joining_date).days / 365.25) + prior
            if total_exp < 2:
                exp_buckets["<2 Years"] += 1
            elif total_exp < 5:
                exp_buckets["2-5 Years"] += 1
            elif total_exp < 10:
                exp_buckets["5-10 Years"] += 1
            else:
                exp_buckets["10+ Years"] += 1

        # 6. Trends
        att_trends = await self.repo.get_attendance_trends(school_id)
        leave_trends = await self.repo.get_monthly_leaves_count(school_id)
        late_trends = await self.repo.get_monthly_lates_count(school_id)
        joining_trends = await self.repo.get_monthly_joining_count(school_id)
        attrition_trends = await self.repo.get_monthly_attrition_count(school_id)

        data = {
            "department_wise_employees": [
                NameCountPair(name=k, count=v) for k, v in dept_emps
            ],
            "department_wise_teachers": [
                NameCountPair(name=k, count=v) for k, v in dept_teachers
            ],
            "gender_distribution": [
                NameCountPair(name=k, count=v) for k, v in gender_data
            ],
            "age_distribution": [
                NameCountPair(name=k, count=v) for k, v in age_buckets.items()
            ],
            "qualification_distribution": [
                NameCountPair(name=k, count=v) for k, v in qual_counts.items()
            ],
            "experience_distribution": [
                NameCountPair(name=k, count=v) for k, v in exp_buckets.items()
            ],
            "attendance_trends": [
                DatePercentPair(date=k, percentage=v) for k, v in att_trends
            ],
            "leave_trends": [MonthCountPair(month=k, count=v) for k, v in leave_trends],
            "late_arrival_trends": [
                MonthCountPair(month=k, count=v) for k, v in late_trends
            ],
            "joining_trends": [
                MonthCountPair(month=k, count=v) for k, v in joining_trends
            ],
            "attrition_trends": [
                MonthCountPair(month=k, count=v) for k, v in attrition_trends
            ],
        }

        response_obj = AnalyticsResponse.model_validate(data)
        await self.cache.set(
            cache_key, response_obj.model_dump(mode="json"), DASHBOARD_CACHE_TTL
        )

        # Audit
        await self.audit.log_action(
            module="teacher_dashboard",
            action="read_analytics",
            entity_name="TeacherDashboard",
            entity_id=school_id,
            user_id=actor.id,
            school_id=school_id,
        )

        return response_obj

    async def get_charts(self, school_id: uuid.UUID, actor: User) -> ChartsResponse:
        cache_key = f"teacher_dashboard:charts:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ChartsResponse.model_validate(cached)

        # We can extract the analytics dataset and convert it into simplified charts labels/values.
        analytics = await self.get_analytics(school_id, actor)

        data = {
            "monthly_employee_joining": [
                ChartItem(label=x.month, value=float(x.count))
                for x in analytics.joining_trends
            ],
            "monthly_teacher_joining": [
                ChartItem(label=x.month, value=float(x.count))
                for x in analytics.joining_trends
            ],  # simplified mapping
            "department_distribution": [
                ChartItem(label=x.name, value=float(x.count))
                for x in analytics.department_wise_employees
            ],
            "attendance_trend": [
                ChartItem(label=x.date.isoformat(), value=x.percentage)
                for x in analytics.attendance_trends
            ],
            "leave_trend": [
                ChartItem(label=x.month, value=float(x.count))
                for x in analytics.leave_trends
            ],
            "qualification_distribution": [
                ChartItem(label=x.name, value=float(x.count))
                for x in analytics.qualification_distribution
            ],
            "experience_distribution": [
                ChartItem(label=x.name, value=float(x.count))
                for x in analytics.experience_distribution
            ],
            "gender_ratio": [
                ChartItem(label=x.name, value=float(x.count))
                for x in analytics.gender_distribution
            ],
            "age_groups": [
                ChartItem(label=x.name, value=float(x.count))
                for x in analytics.age_distribution
            ],
        }

        response_obj = ChartsResponse.model_validate(data)
        await self.cache.set(
            cache_key, response_obj.model_dump(mode="json"), DASHBOARD_CACHE_TTL
        )

        # Audit Charts Access
        await self.audit.log_action(
            module="teacher_dashboard",
            action="read_charts",
            entity_name="TeacherDashboard",
            entity_id=school_id,
            user_id=actor.id,
            school_id=school_id,
        )

        return response_obj
