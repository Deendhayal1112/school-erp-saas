import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.user import User
from app.modules.qualification.enums import QualificationType
from app.modules.teacher_dashboard.constants import DASHBOARD_CACHE_TTL
from app.modules.teacher_dashboard.repository import TeacherDashboardRepository
from app.modules.teacher_dashboard.schemas import DashboardKPIsResponse

logger = logging.getLogger(__name__)


class TeacherDashboardService:
    """
    Service class orchestrating business actions and cache management for Teacher Dashboard KPIs.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TeacherDashboardRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def get_kpis(
        self, school_id: uuid.UUID, actor: User
    ) -> DashboardKPIsResponse:
        cache_key = f"teacher_dashboard:kpis:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return DashboardKPIsResponse.model_validate(cached)

        # 1. Core counters
        total_emp = await self.repo.get_total_employees(school_id)
        total_t = await self.repo.get_total_teachers(school_id)
        teaching = await self.repo.get_teaching_staff_count(school_id)
        non_teaching = await self.repo.get_non_teaching_staff_count(school_id)
        depts = await self.repo.get_departments_count(school_id)
        desgs = await self.repo.get_designations_count(school_id)
        leaves = await self.repo.get_employees_on_leave_today(school_id)

        # 2. Today's attendance
        att_stats = await self.repo.get_today_attendance_stats(school_id)
        present = att_stats["present"]
        absent = att_stats["absent"]
        late = att_stats["late"]

        total_att = present + absent + late
        att_percentage = (
            round(((present + late) / total_att) * 100.0, 2) if total_att > 0 else 0.0
        )

        # 3. Average Experience calculation
        exp_comps = await self.repo.get_average_experience_components(school_id)
        total_exp = 0.0
        today = date.today()
        for joining_date, prior in exp_comps:
            school_exp = (today - joining_date).days / 365.25
            total_exp += max(0.0, school_exp) + prior
        avg_experience = round(total_exp / len(exp_comps), 2) if exp_comps else 0.0

        # 4. Average Qualification level calculation
        qualifications = await self.repo.get_highest_qualifications(school_id)
        score_map = {
            QualificationType.DOCTORATE: 5.0,
            QualificationType.POST_GRADUATION: 4.0,
            QualificationType.GRADUATION: 3.0,
            QualificationType.DIPLOMA: 2.0,
            QualificationType.CERTIFICATION: 2.0,
            QualificationType.SECONDARY: 1.0,
            QualificationType.HIGHER_SECONDARY: 1.0,
            QualificationType.OTHER: 1.0,
        }
        total_qual = sum(score_map.get(q, 1.0) for q in qualifications)
        avg_qualification = (
            round(total_qual / len(qualifications), 2) if qualifications else 0.0
        )

        # 5. Expiry counts
        expiry_counts = await self.repo.get_upcoming_expiry_counts(school_id)
        upcoming_docs = expiry_counts["documents"]
        upcoming_licenses = expiry_counts["licenses"]

        data = {
            "total_employees": total_emp,
            "total_teachers": total_t,
            "teaching_staff": teaching,
            "non_teaching_staff": non_teaching,
            "departments": depts,
            "designations": desgs,
            "employees_on_leave_today": leaves,
            "present_today": present,
            "absent_today": absent,
            "late_today": late,
            "attendance_percentage": att_percentage,
            "average_experience": avg_experience,
            "average_qualification_level": avg_qualification,
            "upcoming_document_expiry": upcoming_docs,
            "upcoming_license_expiry": upcoming_licenses,
        }

        await self.cache.set(cache_key, data, DASHBOARD_CACHE_TTL)

        # Audit Log Action
        await self.audit.log_action(
            module="teacher_dashboard",
            action="read_kpis",
            entity_name="TeacherDashboard",
            entity_id=school_id,
            user_id=actor.id,
            school_id=school_id,
        )

        return DashboardKPIsResponse.model_validate(data)

    async def invalidate_dashboard_cache(self, school_id: uuid.UUID) -> None:
        """Invalidates dashboard, analytics, and reports cache."""
        pattern_keys = [
            f"teacher_dashboard:kpis:{school_id}",
            f"teacher_dashboard:analytics:{school_id}",
            f"teacher_dashboard:charts:{school_id}",
            "teacher_dashboard:reports:*",
        ]
        for key in pattern_keys:
            if "*" in key:
                # We can't do key pattern scan easily in simple client mocks,
                # but we can try invalidating known report patterns
                report_types = [
                    "employees",
                    "teachers",
                    "attendance",
                    "leaves",
                    "qualifications",
                    "experience",
                    "departments",
                    "designations",
                    "document-expiry",
                ]
                for r in report_types:
                    await self.cache.delete(
                        f"teacher_dashboard:reports:{r}:{school_id}"
                    )
            else:
                await self.cache.delete(key)
