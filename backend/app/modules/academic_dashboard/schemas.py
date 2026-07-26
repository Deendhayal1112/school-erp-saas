from pydantic import BaseModel, ConfigDict


class DashboardKPIsResponse(BaseModel):
    total_academic_years: int
    total_terms: int
    total_classes: int
    total_sections: int
    total_subjects: int
    total_subject_groups: int
    total_curriculum: int
    active_curriculum: int
    average_curriculum_completion: float
    active_academic_year: str | None
    active_term: str | None
    active_classes: int

    model_config = ConfigDict(from_attributes=True)


class ClassStudentCount(BaseModel):
    class_id: str
    class_name: str
    student_count: int


class SectionStudentCount(BaseModel):
    section_id: str
    section_name: str
    student_count: int


class ClassSubjectCount(BaseModel):
    class_id: str
    class_name: str
    subject_count: int


class GradeSubjectCount(BaseModel):
    grade: str
    subject_count: int


class CurriculumCompletionStatus(BaseModel):
    curriculum_id: str
    curriculum_name: str
    completion_percentage: float


class WeeklyTeachingHours(BaseModel):
    class_id: str
    class_name: str
    weekly_hours: float


class CreditDistribution(BaseModel):
    subject_name: str
    credits: float


class CoreVsElective(BaseModel):
    core_count: int
    elective_count: int


class SubjectCategoryDistribution(BaseModel):
    category: str
    subject_count: int


class LanguageDistribution(BaseModel):
    language: str
    school_count: int


class AnalyticsResponse(BaseModel):
    students_per_class: list[ClassStudentCount]
    students_per_section: list[SectionStudentCount]
    subjects_per_class: list[ClassSubjectCount]
    subjects_per_grade: list[GradeSubjectCount]
    curriculum_completion: list[CurriculumCompletionStatus]
    weekly_teaching_hours: list[WeeklyTeachingHours]
    credits_distribution: list[CreditDistribution]
    core_vs_elective: CoreVsElective
    subject_distribution: list[SubjectCategoryDistribution]
    language_distribution: list[LanguageDistribution]

    model_config = ConfigDict(from_attributes=True)


class MonthlyAdmissionCount(BaseModel):
    month: str
    admission_count: int


class CurriculumProgressItem(BaseModel):
    curriculum_code: str
    curriculum_name: str
    completion_percentage: float


class ChartClassDistribution(BaseModel):
    class_name: str
    capacity: int
    current_occupancy: int


class TimelineEvent(BaseModel):
    event_name: str
    start_date: str
    end_date: str


class ChartsResponse(BaseModel):
    monthly_admissions: list[MonthlyAdmissionCount]
    curriculum_progress: list[CurriculumProgressItem]
    class_distribution: list[ChartClassDistribution]
    academic_timeline: list[TimelineEvent]

    model_config = ConfigDict(from_attributes=True)


class AcademicSummaryReport(BaseModel):
    total_students: int
    total_classes: int
    total_sections: int
    total_subjects: int
    average_attendance_required: float
    passing_grade_average: float


class ReportItem(BaseModel):
    id: str
    name: str
    code: str
    status: str
    details: str | None = None


class AcademicYearReportResponse(BaseModel):
    academic_year_id: str
    name: str
    code: str
    start_date: str
    end_date: str
    status: str
    total_terms: int
    total_classes: int


class TermReportResponse(BaseModel):
    term_id: str
    name: str
    code: str
    academic_year: str
    status: str
    start_date: str
    end_date: str


class ClassReportResponse(BaseModel):
    class_id: str
    name: str
    code: str
    academic_year: str
    total_sections: int
    total_subjects: int
    total_students: int


class SectionReportResponse(BaseModel):
    section_id: str
    section_name: str
    class_name: str
    capacity: int
    student_count: int


class SubjectReportResponse(BaseModel):
    subject_id: str
    subject_name: str
    subject_code: str
    category: str
    credits: float
    weekly_periods: int
    is_core: bool
    is_elective: bool


class CurriculumReportResponse(BaseModel):
    curriculum_id: str
    curriculum_name: str
    curriculum_code: str
    class_name: str
    subject_name: str
    completion_percentage: float
    total_units: int
    status: str


class SubjectGroupReportResponse(BaseModel):
    subject_group_id: str
    name: str
    code: str
    description: str | None
    total_subjects: int
