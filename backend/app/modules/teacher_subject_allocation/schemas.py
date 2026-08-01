import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.modules.teacher_subject_allocation.enums import AllocationStatus


# --- Teacher Subject Allocation ---
class TeacherSubjectAllocationBase(BaseModel):
    teacher_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    academic_year_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    term_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    class_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    section_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    subject_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    priority: int = Field(default=1, ge=1, examples=[1])
    weekly_period_limit: int = Field(..., ge=1, examples=[5])
    assigned_periods: int = Field(default=0, ge=0, examples=[0])
    preferred_room_id: uuid.UUID | None = Field(None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    preferred_shift_id: uuid.UUID | None = Field(None, examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    is_class_teacher: bool = Field(default=False, examples=[False])
    is_primary_teacher: bool = Field(default=True, examples=[True])
    effective_from: datetime.date = Field(..., examples=["2026-06-01"])
    effective_to: datetime.date | None = Field(None, examples=["2027-05-31"])
    remarks: str | None = Field(None, examples=["Assigned to Grade 10 Physics"])
    status: AllocationStatus = Field(default=AllocationStatus.ACTIVE, examples=["ACTIVE"])


class TeacherSubjectAllocationCreate(TeacherSubjectAllocationBase):
    pass


class TeacherSubjectAllocationUpdate(BaseModel):
    priority: int | None = Field(None, ge=1)
    weekly_period_limit: int | None = Field(None, ge=1)
    assigned_periods: int | None = Field(None, ge=0)
    preferred_room_id: uuid.UUID | None = None
    preferred_shift_id: uuid.UUID | None = None
    is_class_teacher: bool | None = None
    is_primary_teacher: bool | None = None
    effective_from: datetime.date | None = None
    effective_to: datetime.date | None = None
    remarks: str | None = None
    status: AllocationStatus | None = None
    is_active: bool | None = None


class TeacherSubjectAllocationResponse(TeacherSubjectAllocationBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    is_locked: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Teacher Workload ---
class TeacherWorkloadBase(BaseModel):
    teacher_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    maximum_weekly_periods: int = Field(..., ge=1, examples=[24])
    allocated_periods: int = Field(default=0, ge=0, examples=[0])
    remaining_periods: int = Field(..., ge=0, examples=[24])
    daily_limit: int = Field(..., ge=1, examples=[5])
    consecutive_period_limit: int = Field(..., ge=1, examples=[3])


class TeacherWorkloadCreate(TeacherWorkloadBase):
    pass


class TeacherWorkloadUpdate(BaseModel):
    maximum_weekly_periods: int | None = Field(None, ge=1)
    allocated_periods: int | None = Field(None, ge=0)
    remaining_periods: int | None = Field(None, ge=0)
    daily_limit: int | None = Field(None, ge=1)
    consecutive_period_limit: int | None = Field(None, ge=1)
    is_active: bool | None = None


class TeacherWorkloadResponse(TeacherWorkloadBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Subject Qualification ---
class SubjectQualificationBase(BaseModel):
    teacher_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    subject_id: uuid.UUID = Field(..., examples=["497f6eca-6276-4993-bfeb-53cbbbba6f08"])
    qualification_level: str = Field(..., max_length=100, examples=["PostGraduate", "Doctorate"])
    certified: bool = Field(default=False, examples=[True])
    years_of_experience: int = Field(default=0, ge=0, examples=[5])


class SubjectQualificationCreate(SubjectQualificationBase):
    pass


class SubjectQualificationUpdate(BaseModel):
    qualification_level: str | None = Field(None, max_length=100)
    certified: bool | None = None
    years_of_experience: int | None = Field(None, ge=0)
    is_active: bool | None = None


class SubjectQualificationResponse(SubjectQualificationBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Teacher Assignment Summary ---
class TeacherAssignmentSummaryResponse(BaseModel):
    teacher_id: uuid.UUID
    teacher_name: str
    teacher_code: str
    max_weekly_periods: int
    allocated_periods: int
    remaining_periods: int
    assigned_subjects_count: int
    allocations: list[TeacherSubjectAllocationResponse]
