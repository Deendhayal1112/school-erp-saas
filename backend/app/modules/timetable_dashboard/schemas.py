"""
Pydantic v2 schemas for the Timetable Dashboard, Analytics & Reports module.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# KPI Schema
# ---------------------------------------------------------------------------
class TimetableKPIsResponse(BaseModel):
    total_timetables: int
    published_timetables: int
    draft_timetables: int
    total_classes_scheduled: int
    total_teachers_scheduled: int
    total_rooms_utilized: int
    average_teacher_workload: float
    average_room_utilization: float
    total_weekly_periods: int
    substitutions_today: int
    conflicts_resolved: int
    pending_conflicts: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Shared Primitive Schemas
# ---------------------------------------------------------------------------
class NameCountPair(BaseModel):
    name: str
    count: int


class DateCountPair(BaseModel):
    date: date
    count: int


class MonthCountPair(BaseModel):
    month: str
    count: int


class ChartItem(BaseModel):
    label: str
    value: float


# ---------------------------------------------------------------------------
# Analytics Breakdowns & Helper Schemas
# ---------------------------------------------------------------------------
class TeacherWorkloadItem(BaseModel):
    teacher_name: str
    allocated_periods: int
    maximum_weekly_periods: int
    workload_percentage: float


class RoomUtilizationItem(BaseModel):
    room_name: str
    utilization_percentage: float


class SubjectDistributionItem(BaseModel):
    subject_name: str
    period_count: int


class ClassPeriodCountItem(BaseModel):
    class_name: str
    section_name: str
    period_count: int


class TeacherPeriodCountItem(BaseModel):
    teacher_name: str
    period_count: int


class DailyHoursItem(BaseModel):
    day_name: str
    hours: float


class WeeklyHoursItem(BaseModel):
    week_start: date
    hours: float


class TimetableUtilizationItem(BaseModel):
    term_name: str
    published_count: int
    total_count: int
    utilization_percentage: float


class AnalyticsResponse(BaseModel):
    teacher_workload_distribution: list[NameCountPair]
    room_utilization: list[RoomUtilizationItem]
    subject_distribution: list[SubjectDistributionItem]
    class_wise_period_count: list[ClassPeriodCountItem]
    teacher_wise_period_count: list[TeacherPeriodCountItem]
    daily_teaching_hours: list[DailyHoursItem]
    weekly_teaching_hours: list[WeeklyHoursItem]
    timetable_utilization: list[TimetableUtilizationItem]
    substitution_trends: list[MonthCountPair]
    conflict_trends: list[MonthCountPair]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Charts Response
# ---------------------------------------------------------------------------
class HeatmapCell(BaseModel):
    day_name: str
    time_slot: str
    count: int


class ChartsResponse(BaseModel):
    weekly_timetable_heatmap: list[HeatmapCell]
    teacher_workload: list[ChartItem]
    room_occupancy: list[ChartItem]
    subject_distribution: list[ChartItem]
    daily_schedule: list[ChartItem]
    conflict_statistics: list[ChartItem]
    substitution_statistics: list[ChartItem]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Reports Item Schemas
# ---------------------------------------------------------------------------
class MasterTimetableReportItem(BaseModel):
    id: uuid.UUID
    class_name: str
    section_name: str
    day_name: str
    time_slot_name: str
    period_number: int
    teacher_name: str
    subject_name: str
    room_name: str | None
    lesson_type: str

    model_config = ConfigDict(from_attributes=True)


class ClassTimetableReportItem(BaseModel):
    id: uuid.UUID
    class_name: str
    section_name: str
    day_name: str
    time_slot_name: str
    period_number: int
    teacher_name: str
    subject_name: str
    room_name: str | None
    lesson_type: str

    model_config = ConfigDict(from_attributes=True)


class TeacherTimetableReportItem(BaseModel):
    id: uuid.UUID
    teacher_name: str
    day_name: str
    time_slot_name: str
    period_number: int
    class_name: str
    section_name: str
    subject_name: str
    room_name: str | None
    lesson_type: str

    model_config = ConfigDict(from_attributes=True)


class RoomUtilizationReportItem(BaseModel):
    room_name: str
    room_type: str
    capacity: int
    scheduled_periods: int
    total_slots: int
    utilization_percentage: float

    model_config = ConfigDict(from_attributes=True)


class TeacherWorkloadReportItem(BaseModel):
    teacher_name: str
    maximum_weekly_periods: int
    allocated_periods: int
    remaining_periods: int
    daily_limit: int
    consecutive_period_limit: int
    utilization_percentage: float

    model_config = ConfigDict(from_attributes=True)


class ConflictReportItem(BaseModel):
    id: uuid.UUID
    conflict_type: str
    severity: str
    class_name: str
    section_name: str
    teacher_name: str
    subject_name: str
    day_name: str
    time_slot_name: str
    description: str
    status: str
    detected_at: datetime
    resolved_at: datetime | None
    resolver_name: str | None

    model_config = ConfigDict(from_attributes=True)


class SubstitutionReportItem(BaseModel):
    id: uuid.UUID
    original_teacher_name: str
    substitute_teacher_name: str
    class_name: str
    section_name: str
    subject_name: str
    day_name: str
    time_slot_name: str
    reason: str
    substitution_type: str
    effective_date: date
    status: str
    approved_by_name: str | None
    approved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
