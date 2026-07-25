import uuid
from datetime import date

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    total_students: int = Field(..., description="Total student count")
    active_students: int = Field(..., description="Active student count")
    inactive_students: int = Field(..., description="Inactive student count")
    new_admissions: int = Field(..., description="Count of new admissions")
    graduated_students: int = Field(..., description="Count of graduated students")
    transferred_students: int = Field(..., description="Count of transferred students")
    medical_alerts: int = Field(
        ..., description="Count of medical records with critical allergies or alerts"
    )
    pending_documents: int = Field(
        ..., description="Count of pending/unverified documents"
    )


class GenderAnalyticsResponse(BaseModel):
    gender: str = Field(..., description="Gender label")
    count: int = Field(..., description="Student count")


class ClasswiseAnalyticsResponse(BaseModel):
    class_id: uuid.UUID = Field(..., description="Class UUID reference")
    count: int = Field(..., description="Student count")


class SectionwiseAnalyticsResponse(BaseModel):
    section_id: uuid.UUID = Field(..., description="Section UUID reference")
    count: int = Field(..., description="Student count")


class BloodGroupAnalyticsResponse(BaseModel):
    blood_group: str = Field(..., description="Blood group code")
    count: int = Field(..., description="Student count")


class AdmissionAnalyticsResponse(BaseModel):
    date_label: str = Field(..., description="Month or Date label")
    count: int = Field(..., description="Admission count")


class PromotionAnalyticsResponse(BaseModel):
    academic_year_id: uuid.UUID = Field(..., description="Academic year reference")
    count: int = Field(..., description="Promotion count")


class GraduationAnalyticsResponse(BaseModel):
    academic_year_id: uuid.UUID = Field(..., description="Academic year reference")
    count: int = Field(..., description="Graduation count")


class SearchStudentItem(BaseModel):
    id: uuid.UUID
    admission_number: str
    roll_number: str | None
    first_name: str
    last_name: str
    email: str | None


class SearchGuardianItem(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str


class GlobalSearchResponse(BaseModel):
    students: list[SearchStudentItem] = Field(default_factory=list)
    guardians: list[SearchGuardianItem] = Field(default_factory=list)


# Report Items
class StudentReportItem(BaseModel):
    id: uuid.UUID
    admission_number: str
    roll_number: str | None
    first_name: str
    last_name: str
    status: str
    joined_date: date


class AdmissionReportItem(BaseModel):
    id: uuid.UUID
    application_number: str
    student_name: str
    status: str
    academic_year: str


class MedicalReportItem(BaseModel):
    student_name: str
    blood_group: str | None
    allergies_count: int
    vaccinations_count: int


class GuardianReportItem(BaseModel):
    student_name: str
    guardian_name: str
    relationship: str
    phone: str
    is_primary: bool


class DocumentReportItem(BaseModel):
    student_name: str
    document_type: str
    status: str
    is_verified: bool


class PromotionReportItem(BaseModel):
    student_name: str
    from_year: str | None
    to_year: str | None
    remarks: str | None


class GraduationReportItem(BaseModel):
    student_name: str
    graduation_date: date | None
    remarks: str | None


class AlumniReportItem(BaseModel):
    student_name: str
    graduation_date: date | None
    phone: str | None
