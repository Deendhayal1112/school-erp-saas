import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.academic_settings.enums import AcademicSettingsStatus


class AcademicSettingsBase(BaseModel):
    academic_year_id: uuid.UUID
    default_term_id: uuid.UUID | None = None

    default_language: str = Field(default="English", min_length=1, max_length=50)
    grading_system: str = Field(default="GPA", min_length=1, max_length=50)
    attendance_calculation_method: str = Field(
        default="DAILY", min_length=1, max_length=50
    )
    promotion_policy: str | None = None

    passing_percentage: float = Field(default=40.0, ge=0.0, le=100.0)
    minimum_attendance_percentage: float = Field(default=75.0, ge=0.0, le=100.0)

    maximum_subjects_per_day: int = Field(default=6, ge=1)
    maximum_periods_per_day: int = Field(default=8, ge=1)
    working_days_per_week: int = Field(default=5, ge=1, le=7)

    academic_timezone: str = Field(default="UTC", min_length=1, max_length=50)
    academic_calendar_type: str = Field(default="SEMESTER", min_length=1, max_length=50)
    week_start_day: str = Field(default="MONDAY", min_length=1, max_length=20)

    allow_subject_electives: bool = Field(default=True)
    allow_cross_section_subjects: bool = Field(default=False)
    allow_student_transfers: bool = Field(default=True)
    allow_mid_year_admission: bool = Field(default=True)

    auto_generate_roll_numbers: bool = Field(default=True)
    roll_number_prefix: str | None = Field(default=None, max_length=20)
    roll_number_padding: int = Field(default=4, ge=1)

    default_class_capacity: int = Field(default=40, ge=1)


class AcademicSettingsCreate(AcademicSettingsBase):
    pass


class AcademicSettingsUpdate(BaseModel):
    default_term_id: uuid.UUID | None = None

    default_language: str | None = Field(None, min_length=1, max_length=50)
    grading_system: str | None = Field(None, min_length=1, max_length=50)
    attendance_calculation_method: str | None = Field(None, min_length=1, max_length=50)
    promotion_policy: str | None = None

    passing_percentage: float | None = Field(None, ge=0.0, le=100.0)
    minimum_attendance_percentage: float | None = Field(None, ge=0.0, le=100.0)

    maximum_subjects_per_day: int | None = Field(None, ge=1)
    maximum_periods_per_day: int | None = Field(None, ge=1)
    working_days_per_week: int | None = Field(None, ge=1, le=7)

    academic_timezone: str | None = Field(None, min_length=1, max_length=50)
    academic_calendar_type: str | None = Field(None, min_length=1, max_length=50)
    week_start_day: str | None = Field(None, min_length=1, max_length=20)

    allow_subject_electives: bool | None = None
    allow_cross_section_subjects: bool | None = None
    allow_student_transfers: bool | None = None
    allow_mid_year_admission: bool | None = None

    auto_generate_roll_numbers: bool | None = None
    roll_number_prefix: str | None = Field(None, max_length=20)
    roll_number_padding: int | None = Field(None, ge=1)

    default_class_capacity: int | None = Field(None, ge=1)


class AcademicSettingsResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    default_term_id: uuid.UUID | None

    default_language: str
    grading_system: str
    attendance_calculation_method: str
    promotion_policy: str | None

    passing_percentage: float
    minimum_attendance_percentage: float

    maximum_subjects_per_day: int
    maximum_periods_per_day: int
    working_days_per_week: int

    academic_timezone: str
    academic_calendar_type: str
    week_start_day: str

    allow_subject_electives: bool
    allow_cross_section_subjects: bool
    allow_student_transfers: bool
    allow_mid_year_admission: bool

    auto_generate_roll_numbers: bool
    roll_number_prefix: str | None
    roll_number_padding: int

    default_class_capacity: int

    status: AcademicSettingsStatus
    is_active: bool
    is_locked: bool

    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
