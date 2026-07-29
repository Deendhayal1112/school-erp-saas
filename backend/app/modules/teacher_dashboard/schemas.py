import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# KPI Schema
# ---------------------------------------------------------------------------
class DashboardKPIsResponse(BaseModel):
    total_employees: int
    total_teachers: int
    teaching_staff: int
    non_teaching_staff: int
    departments: int
    designations: int
    employees_on_leave_today: int
    present_today: int
    absent_today: int
    late_today: int
    attendance_percentage: float
    average_experience: float
    average_qualification_level: float
    upcoming_document_expiry: int
    upcoming_license_expiry: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Analytics Breakdowns & Helper Schemas
# ---------------------------------------------------------------------------
class NameCountPair(BaseModel):
    name: str
    count: int


class DatePercentPair(BaseModel):
    date: date
    percentage: float


class DateCountPair(BaseModel):
    date: date
    count: int


class MonthCountPair(BaseModel):
    month: str
    count: int


class AnalyticsResponse(BaseModel):
    department_wise_employees: list[NameCountPair]
    department_wise_teachers: list[NameCountPair]
    gender_distribution: list[NameCountPair]
    age_distribution: list[NameCountPair]
    qualification_distribution: list[NameCountPair]
    experience_distribution: list[NameCountPair]
    attendance_trends: list[DatePercentPair]
    leave_trends: list[MonthCountPair]
    late_arrival_trends: list[MonthCountPair]
    joining_trends: list[MonthCountPair]
    attrition_trends: list[MonthCountPair]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Charts Response
# ---------------------------------------------------------------------------
class ChartItem(BaseModel):
    label: str
    value: float


class ChartsResponse(BaseModel):
    monthly_employee_joining: list[ChartItem]
    monthly_teacher_joining: list[ChartItem]
    department_distribution: list[ChartItem]
    attendance_trend: list[ChartItem]
    leave_trend: list[ChartItem]
    qualification_distribution: list[ChartItem]
    experience_distribution: list[ChartItem]
    gender_ratio: list[ChartItem]
    age_groups: list[ChartItem]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Reports Item Schemas
# ---------------------------------------------------------------------------
class EmployeeReportItem(BaseModel):
    id: uuid.UUID
    employee_number: str
    first_name: str
    last_name: str
    email: str
    phone: str
    gender: str
    date_of_birth: date
    joining_date: date
    employment_status: str
    employee_type: str
    department_name: str
    designation_name: str

    model_config = ConfigDict(from_attributes=True)


class TeacherReportItem(BaseModel):
    id: uuid.UUID
    teacher_code: str
    teacher_type: str
    employment_mode: str
    official_email: str | None
    first_name: str
    last_name: str
    joining_date: date
    department_name: str
    teaching_experience_years: int
    highest_qualification: str | None

    model_config = ConfigDict(from_attributes=True)


class QualificationReportItem(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    qualification_type: str
    qualification_name: str
    degree: str | None
    specialization: str | None
    institution_name: str
    passing_year: int | None
    percentage: float | None
    cgpa: float | None

    model_config = ConfigDict(from_attributes=True)


class ExperienceReportItem(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    organization_name: str
    designation: str
    start_date: date
    end_date: date | None
    currently_working: bool
    experience_years: int | None
    experience_months: int | None

    model_config = ConfigDict(from_attributes=True)


class AttendanceReportItem(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    attendance_date: date
    check_in_time: datetime | None
    check_out_time: datetime | None
    working_hours: float
    late_minutes: int
    early_departure_minutes: int
    overtime_minutes: int
    status: str
    source: str

    model_config = ConfigDict(from_attributes=True)


class LeaveReportItem(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    leave_type_name: str
    start_date: date
    end_date: date
    status: str
    reason: str | None
    approved_by_name: str | None

    model_config = ConfigDict(from_attributes=True)


class DepartmentReportItem(BaseModel):
    id: uuid.UUID
    department_code: str
    department_name: str
    employee_count: int
    teacher_count: int

    model_config = ConfigDict(from_attributes=True)


class DesignationReportItem(BaseModel):
    id: uuid.UUID
    designation_code: str
    designation_name: str
    department_name: str
    employee_count: int

    model_config = ConfigDict(from_attributes=True)


class DocumentExpiryReportItem(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    document_name: str
    document_type: str
    expiry_date: date
    is_expired: bool
    is_mandatory: bool

    model_config = ConfigDict(from_attributes=True)
