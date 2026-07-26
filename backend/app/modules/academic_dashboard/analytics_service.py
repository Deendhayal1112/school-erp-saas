import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.modules.academic_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.academic_dashboard.repository import AcademicDashboardRepository
from app.modules.academic_dashboard.schemas import AnalyticsResponse


class AcademicAnalyticsService:
    """
    Service class orchestrating business actions and cache management for Academic Analytics metrics.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AcademicDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_analytics(
        self, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AnalyticsResponse:
        cache_key = f"academic_dashboard:analytics:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AnalyticsResponse.model_validate(cached)

        students_per_class = await self.repo.get_students_per_class(school_id)
        students_per_section = await self.repo.get_students_per_section(school_id)
        subjects_per_class = await self.repo.get_subjects_per_class(school_id)
        # Subjects per grade is functionally the same as subjects per class in our system
        subjects_per_grade = [
            {"grade": item["class_name"], "subject_count": item["subject_count"]}
            for item in subjects_per_class
        ]
        curriculum_completion = [
            {
                "curriculum_id": item[
                    "curriculum_code"
                ],  # use code as placeholder id if needed
                "curriculum_name": item["curriculum_name"],
                "completion_percentage": item["completion_percentage"],
            }
            for item in await self.repo.get_curriculum_progress(school_id)
        ]
        weekly_teaching_hours = await self.repo.get_weekly_teaching_hours(school_id)
        credits_distribution = await self.repo.get_credits_distribution(school_id)
        core_vs_elective = await self.repo.get_core_vs_elective(school_id)
        subject_distribution = await self.repo.get_subject_distribution(school_id)
        language_distribution = await self.repo.get_language_distribution(school_id)

        data = {
            "students_per_class": students_per_class,
            "students_per_section": students_per_section,
            "subjects_per_class": subjects_per_class,
            "subjects_per_grade": subjects_per_grade,
            "curriculum_completion": curriculum_completion,
            "weekly_teaching_hours": weekly_teaching_hours,
            "credits_distribution": credits_distribution,
            "core_vs_elective": core_vs_elective,
            "subject_distribution": subject_distribution,
            "language_distribution": language_distribution,
        }

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit Log
        await self.audit.log_action(
            module="academic_dashboard",
            action="read_analytics",
            entity_name="AcademicDashboard",
            entity_id=school_id,
            user_id=user_id,
            school_id=school_id,
        )

        return AnalyticsResponse.model_validate(data)
