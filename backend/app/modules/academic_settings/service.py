import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditLogService
from app.cache.service import CacheService
from app.models.school import School
from app.modules.academic_settings.enums import AcademicSettingsStatus
from app.modules.academic_settings.exceptions import (
    AcademicSettingsNotFoundException,
    InvalidAcademicSettingsException,
)
from app.modules.academic_settings.models import AcademicSettings
from app.modules.academic_settings.repository import AcademicSettingsRepository
from app.modules.academic_settings.schemas import (
    AcademicSettingsCreate,
    AcademicSettingsUpdate,
)
from app.modules.academic_settings.validators import validate_academic_settings_data
from app.modules.academic_year.enums import AcademicYearStatus
from app.modules.academic_year.models import AcademicYear
from app.modules.term.enums import TermStatus
from app.modules.term.models import Term


class AcademicSettingsService:
    """
    Service class orchestrating business actions and cache invalidation for AcademicSettings.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AcademicSettingsRepository(db)
        self.audit = AuditLogService(db)
        self.cache = CacheService()

    async def _invalidate_cache(
        self, school_id: uuid.UUID, settings_id: uuid.UUID | None = None
    ) -> None:
        """Clears cached list, active, and detail lookup indices."""
        await self.cache.delete_pattern(f"academic_settings:list:{school_id}*")
        await self.cache.delete(f"academic_settings:active:{school_id}")
        if settings_id:
            await self.cache.delete(f"academic_settings:detail:{settings_id}")
        await self.cache.delete_pattern(f"academic_dashboard:*:{school_id}*")

    async def create_settings(
        self,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AcademicSettingsCreate,
    ) -> AcademicSettings:
        # 1. School must exist and be active
        school = await self.db.get(School, school_id)
        if not school or school.status != "active":
            raise InvalidAcademicSettingsException(
                "School does not exist or is inactive."
            )

        # 2. Validate input constraints
        validate_academic_settings_data(
            passing_percentage=data.passing_percentage,
            minimum_attendance_percentage=data.minimum_attendance_percentage,
            maximum_subjects_per_day=data.maximum_subjects_per_day,
            maximum_periods_per_day=data.maximum_periods_per_day,
            working_days_per_week=data.working_days_per_week,
            roll_number_padding=data.roll_number_padding,
            default_class_capacity=data.default_class_capacity,
            academic_timezone=data.academic_timezone,
        )

        # 3. Academic Year must exist and be ACTIVE
        ay = await self.db.get(AcademicYear, data.academic_year_id)
        if not ay or ay.school_id != school_id or ay.is_deleted:
            raise InvalidAcademicSettingsException("Academic Year does not exist.")
        if ay.status != AcademicYearStatus.ACTIVE:
            raise InvalidAcademicSettingsException("Only ACTIVE Academic Year allowed.")

        # 4. Default Term must belong to Academic Year and be ACTIVE
        if data.default_term_id:
            term = await self.db.get(Term, data.default_term_id)
            if (
                not term
                or term.school_id != school_id
                or term.academic_year_id != data.academic_year_id
                or term.is_deleted
            ):
                raise InvalidAcademicSettingsException(
                    "Default Term does not exist or does not belong to Academic Year."
                )
            if term.status != TermStatus.ACTIVE:
                raise InvalidAcademicSettingsException(
                    "Only ACTIVE Term allowed as default."
                )

        # 5. Check if settings already exists for this Academic Year
        conflict = await self.repo.get_by_year(school_id, data.academic_year_id)
        if conflict:
            raise InvalidAcademicSettingsException(
                f"Academic settings for year '{ay.name}' already exists."
            )

        # Enforce "Only one ACTIVE Academic Settings per School"
        # If there's an existing ACTIVE settings config, set it to INACTIVE
        active_settings = await self.repo.get_active(school_id)
        if active_settings:
            active_settings.status = AcademicSettingsStatus.INACTIVE
            active_settings.is_active = False
            await self.repo.update(active_settings)

        settings = AcademicSettings(
            school_id=school_id,
            academic_year_id=data.academic_year_id,
            default_term_id=data.default_term_id,
            default_language=data.default_language,
            grading_system=data.grading_system,
            attendance_calculation_method=data.attendance_calculation_method,
            promotion_policy=data.promotion_policy,
            passing_percentage=data.passing_percentage,
            minimum_attendance_percentage=data.minimum_attendance_percentage,
            maximum_subjects_per_day=data.maximum_subjects_per_day,
            maximum_periods_per_day=data.maximum_periods_per_day,
            working_days_per_week=data.working_days_per_week,
            academic_timezone=data.academic_timezone,
            academic_calendar_type=data.academic_calendar_type,
            week_start_day=data.week_start_day,
            allow_subject_electives=data.allow_subject_electives,
            allow_cross_section_subjects=data.allow_cross_section_subjects,
            allow_student_transfers=data.allow_student_transfers,
            allow_mid_year_admission=data.allow_mid_year_admission,
            auto_generate_roll_numbers=data.auto_generate_roll_numbers,
            roll_number_prefix=data.roll_number_prefix,
            roll_number_padding=data.roll_number_padding,
            default_class_capacity=data.default_class_capacity,
            status=AcademicSettingsStatus.ACTIVE,
            is_active=True,
            is_locked=False,
            created_by=user_id,
        )

        await self.repo.create(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id)

        # Audit
        await self.audit.log_action(
            module="academic_settings",
            action="create",
            entity_name="AcademicSettings",
            entity_id=settings.id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def update_settings(
        self,
        settings_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AcademicSettingsUpdate,
    ) -> AcademicSettings:
        settings = await self.repo.get_by_id(settings_id)
        if not settings or settings.school_id != school_id:
            raise AcademicSettingsNotFoundException()

        # Locked settings cannot be modified.
        if settings.is_locked:
            raise InvalidAcademicSettingsException(
                "Cannot modify locked Academic Settings."
            )

        # Fallbacks for validation
        passing_percentage = (
            data.passing_percentage
            if data.passing_percentage is not None
            else settings.passing_percentage
        )
        minimum_attendance_percentage = (
            data.minimum_attendance_percentage
            if data.minimum_attendance_percentage is not None
            else settings.minimum_attendance_percentage
        )
        maximum_subjects_per_day = (
            data.maximum_subjects_per_day
            if data.maximum_subjects_per_day is not None
            else settings.maximum_subjects_per_day
        )
        maximum_periods_per_day = (
            data.maximum_periods_per_day
            if data.maximum_periods_per_day is not None
            else settings.maximum_periods_per_day
        )
        working_days_per_week = (
            data.working_days_per_week
            if data.working_days_per_week is not None
            else settings.working_days_per_week
        )
        roll_number_padding = (
            data.roll_number_padding
            if data.roll_number_padding is not None
            else settings.roll_number_padding
        )
        default_class_capacity = (
            data.default_class_capacity
            if data.default_class_capacity is not None
            else settings.default_class_capacity
        )
        academic_timezone = (
            data.academic_timezone
            if data.academic_timezone is not None
            else settings.academic_timezone
        )

        validate_academic_settings_data(
            passing_percentage=passing_percentage,
            minimum_attendance_percentage=minimum_attendance_percentage,
            maximum_subjects_per_day=maximum_subjects_per_day,
            maximum_periods_per_day=maximum_periods_per_day,
            working_days_per_week=working_days_per_week,
            roll_number_padding=roll_number_padding,
            default_class_capacity=default_class_capacity,
            academic_timezone=academic_timezone,
        )

        # Validate default term if updated
        if data.default_term_id:
            term = await self.db.get(Term, data.default_term_id)
            if (
                not term
                or term.school_id != school_id
                or term.academic_year_id != settings.academic_year_id
                or term.is_deleted
            ):
                raise InvalidAcademicSettingsException(
                    "Default Term does not exist or does not belong to academic year."
                )
            if term.status != TermStatus.ACTIVE:
                raise InvalidAcademicSettingsException(
                    "Only ACTIVE Term allowed as default."
                )
            settings.default_term_id = data.default_term_id

        if data.default_language is not None:
            settings.default_language = data.default_language
        if data.grading_system is not None:
            settings.grading_system = data.grading_system
        if data.attendance_calculation_method is not None:
            settings.attendance_calculation_method = data.attendance_calculation_method
        if data.promotion_policy is not None:
            settings.promotion_policy = data.promotion_policy
        if data.passing_percentage is not None:
            settings.passing_percentage = data.passing_percentage
        if data.minimum_attendance_percentage is not None:
            settings.minimum_attendance_percentage = data.minimum_attendance_percentage
        if data.maximum_subjects_per_day is not None:
            settings.maximum_subjects_per_day = data.maximum_subjects_per_day
        if data.maximum_periods_per_day is not None:
            settings.maximum_periods_per_day = data.maximum_periods_per_day
        if data.working_days_per_week is not None:
            settings.working_days_per_week = data.working_days_per_week
        if data.academic_timezone is not None:
            settings.academic_timezone = data.academic_timezone
        if data.academic_calendar_type is not None:
            settings.academic_calendar_type = data.academic_calendar_type
        if data.week_start_day is not None:
            settings.week_start_day = data.week_start_day
        if data.allow_subject_electives is not None:
            settings.allow_subject_electives = data.allow_subject_electives
        if data.allow_cross_section_subjects is not None:
            settings.allow_cross_section_subjects = data.allow_cross_section_subjects
        if data.allow_student_transfers is not None:
            settings.allow_student_transfers = data.allow_student_transfers
        if data.allow_mid_year_admission is not None:
            settings.allow_mid_year_admission = data.allow_mid_year_admission
        if data.auto_generate_roll_numbers is not None:
            settings.auto_generate_roll_numbers = data.auto_generate_roll_numbers
        if data.roll_number_prefix is not None:
            settings.roll_number_prefix = data.roll_number_prefix
        if data.roll_number_padding is not None:
            settings.roll_number_padding = data.roll_number_padding
        if data.default_class_capacity is not None:
            settings.default_class_capacity = data.default_class_capacity

        settings.updated_by = user_id
        await self.repo.update(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id, settings_id)

        # Audit
        await self.audit.log_action(
            module="academic_settings",
            action="update",
            entity_name="AcademicSettings",
            entity_id=settings_id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def activate_settings(
        self, settings_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicSettings:
        settings = await self.repo.get_by_id(settings_id)
        if not settings or settings.school_id != school_id:
            raise AcademicSettingsNotFoundException()

        # Archived Settings cannot be activated.
        if settings.status == AcademicSettingsStatus.ARCHIVED:
            raise InvalidAcademicSettingsException(
                "Cannot activate archived Academic Settings."
            )

        # Set any other ACTIVE config for the school to INACTIVE
        active_settings = await self.repo.get_active(school_id)
        if active_settings and active_settings.id != settings_id:
            active_settings.status = AcademicSettingsStatus.INACTIVE
            active_settings.is_active = False
            await self.repo.update(active_settings)

        settings.status = AcademicSettingsStatus.ACTIVE
        settings.is_active = True
        settings.updated_by = user_id
        await self.repo.update(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id, settings_id)

        await self.audit.log_action(
            module="academic_settings",
            action="activate",
            entity_name="AcademicSettings",
            entity_id=settings_id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def deactivate_settings(
        self, settings_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicSettings:
        settings = await self.repo.get_by_id(settings_id)
        if not settings or settings.school_id != school_id:
            raise AcademicSettingsNotFoundException()

        settings.status = AcademicSettingsStatus.INACTIVE
        settings.is_active = False
        settings.updated_by = user_id
        await self.repo.update(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id, settings_id)

        await self.audit.log_action(
            module="academic_settings",
            action="deactivate",
            entity_name="AcademicSettings",
            entity_id=settings_id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def lock_settings(
        self, settings_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicSettings:
        settings = await self.repo.get_by_id(settings_id)
        if not settings or settings.school_id != school_id:
            raise AcademicSettingsNotFoundException()

        settings.is_locked = True
        settings.updated_by = user_id
        await self.repo.update(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id, settings_id)

        await self.audit.log_action(
            module="academic_settings",
            action="lock",
            entity_name="AcademicSettings",
            entity_id=settings_id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def unlock_settings(
        self, settings_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicSettings:
        settings = await self.repo.get_by_id(settings_id)
        if not settings or settings.school_id != school_id:
            raise AcademicSettingsNotFoundException()

        settings.is_locked = False
        settings.updated_by = user_id
        await self.repo.update(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id, settings_id)

        await self.audit.log_action(
            module="academic_settings",
            action="unlock",
            entity_name="AcademicSettings",
            entity_id=settings_id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def archive_settings(
        self, settings_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID
    ) -> AcademicSettings:
        settings = await self.repo.get_by_id(settings_id)
        if not settings or settings.school_id != school_id:
            raise AcademicSettingsNotFoundException()

        settings.status = AcademicSettingsStatus.ARCHIVED
        settings.is_active = False
        settings.updated_by = user_id
        await self.repo.update(settings)
        await self.db.flush()

        await self._invalidate_cache(school_id, settings_id)

        await self.audit.log_action(
            module="academic_settings",
            action="archive",
            entity_name="AcademicSettings",
            entity_id=settings_id,
            user_id=user_id,
            school_id=school_id,
        )

        return settings

    async def get_active_cached(self, school_id: uuid.UUID) -> AcademicSettings | None:
        cache_key = f"academic_settings:active:{school_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return AcademicSettings(
                id=uuid.UUID(cached["id"]),
                school_id=uuid.UUID(cached["school_id"]),
                academic_year_id=uuid.UUID(cached["academic_year_id"]),
                default_term_id=uuid.UUID(cached["default_term_id"])
                if cached["default_term_id"]
                else None,
                default_language=cached["default_language"],
                grading_system=cached["grading_system"],
                attendance_calculation_method=cached["attendance_calculation_method"],
                promotion_policy=cached["promotion_policy"],
                passing_percentage=cached["passing_percentage"],
                minimum_attendance_percentage=cached["minimum_attendance_percentage"],
                maximum_subjects_per_day=cached["maximum_subjects_per_day"],
                maximum_periods_per_day=cached["maximum_periods_per_day"],
                working_days_per_week=cached["working_days_per_week"],
                academic_timezone=cached["academic_timezone"],
                academic_calendar_type=cached["academic_calendar_type"],
                week_start_day=cached["week_start_day"],
                allow_subject_electives=cached["allow_subject_electives"],
                allow_cross_section_subjects=cached["allow_cross_section_subjects"],
                allow_student_transfers=cached["allow_student_transfers"],
                allow_mid_year_admission=cached["allow_mid_year_admission"],
                auto_generate_roll_numbers=cached["auto_generate_roll_numbers"],
                roll_number_prefix=cached["roll_number_prefix"],
                roll_number_padding=cached["roll_number_padding"],
                default_class_capacity=cached["default_class_capacity"],
                status=AcademicSettingsStatus(cached["status"]),
                is_active=cached["is_active"],
                is_locked=cached["is_locked"],
            )

        settings = await self.repo.get_active(school_id)
        if settings:
            state = {
                "id": str(settings.id),
                "school_id": str(settings.school_id),
                "academic_year_id": str(settings.academic_year_id),
                "default_term_id": str(settings.default_term_id)
                if settings.default_term_id
                else None,
                "default_language": settings.default_language,
                "grading_system": settings.grading_system,
                "attendance_calculation_method": settings.attendance_calculation_method,
                "promotion_policy": settings.promotion_policy,
                "passing_percentage": float(settings.passing_percentage),
                "minimum_attendance_percentage": float(
                    settings.minimum_attendance_percentage
                ),
                "maximum_subjects_per_day": settings.maximum_subjects_per_day,
                "maximum_periods_per_day": settings.maximum_periods_per_day,
                "working_days_per_week": settings.working_days_per_week,
                "academic_timezone": settings.academic_timezone,
                "academic_calendar_type": settings.academic_calendar_type,
                "week_start_day": settings.week_start_day,
                "allow_subject_electives": settings.allow_subject_electives,
                "allow_cross_section_subjects": settings.allow_cross_section_subjects,
                "allow_student_transfers": settings.allow_student_transfers,
                "allow_mid_year_admission": settings.allow_mid_year_admission,
                "auto_generate_roll_numbers": settings.auto_generate_roll_numbers,
                "roll_number_prefix": settings.roll_number_prefix,
                "roll_number_padding": settings.roll_number_padding,
                "default_class_capacity": settings.default_class_capacity,
                "status": settings.status.value,
                "is_active": settings.is_active,
                "is_locked": settings.is_locked,
            }
            await self.cache.set(cache_key, state, 3600)

        return settings
