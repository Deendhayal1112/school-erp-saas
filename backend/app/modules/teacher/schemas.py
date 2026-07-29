import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.teacher.enums import EmploymentMode, TeacherType


class TeacherBase(BaseModel):
    teacher_code: str = Field(..., max_length=50)
    teacher_type: TeacherType
    employment_mode: EmploymentMode
    joining_academic_year_id: uuid.UUID | None = None
    primary_department_id: uuid.UUID
    staff_room: str | None = Field(None, max_length=100)
    official_email: str | None = Field(None, max_length=255)
    extension_number: str | None = Field(None, max_length=20)
    office_location: str | None = Field(None, max_length=200)
    bio: str | None = None
    teaching_experience_years: int = Field(0, ge=0)
    highest_qualification: str | None = Field(None, max_length=150)
    specialization: str | None = Field(None, max_length=150)
    subject_preferences: list[str] | None = None
    class_teacher_preference: str | None = Field(None, max_length=100)
    max_teaching_hours_per_week: int = Field(40, gt=0)
    is_class_teacher: bool = False
    is_subject_teacher: bool = True
    is_exam_evaluator: bool = False
    is_archived: bool = False


class TeacherCreate(TeacherBase):
    employee_id: uuid.UUID


class TeacherUpdate(BaseModel):
    teacher_code: str | None = Field(None, max_length=50)
    teacher_type: TeacherType | None = None
    employment_mode: EmploymentMode | None = None
    joining_academic_year_id: uuid.UUID | None = None
    primary_department_id: uuid.UUID | None = None
    staff_room: str | None = Field(None, max_length=100)
    official_email: str | None = Field(None, max_length=255)
    extension_number: str | None = Field(None, max_length=20)
    office_location: str | None = Field(None, max_length=200)
    bio: str | None = None
    teaching_experience_years: int | None = Field(None, ge=0)
    highest_qualification: str | None = Field(None, max_length=150)
    specialization: str | None = Field(None, max_length=150)
    subject_preferences: list[str] | None = None
    class_teacher_preference: str | None = Field(None, max_length=100)
    max_teaching_hours_per_week: int | None = Field(None, gt=0)
    is_class_teacher: bool | None = None
    is_subject_teacher: bool | None = None
    is_exam_evaluator: bool | None = None
    is_archived: bool | None = None


class TeacherResponse(TeacherBase):
    id: uuid.UUID
    school_id: uuid.UUID
    employee_id: uuid.UUID
    is_active: bool
    is_locked: bool
    is_deleted: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
