import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.student_medical.enums import AllergySeverity, BloodGroup


# ==========================================
# Allergy Schemas
# ==========================================
class AllergyBase(BaseModel):
    allergy_name: str = Field(..., max_length=100, description="Name of allergen")
    severity: AllergySeverity = Field(
        AllergySeverity.LOW, description="Severity degree"
    )
    reaction: str | None = Field(None, max_length=200, description="Symptoms/reaction")
    treatment: str | None = Field(
        None, max_length=200, description="First-aid treatment"
    )
    remarks: str | None = Field(None, description="Optional annotations")


class AllergyCreate(AllergyBase):
    pass


class AllergyResponse(AllergyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    medical_record_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# Vaccination Schemas
# ==========================================
class VaccinationBase(BaseModel):
    vaccine_name: str = Field(..., max_length=100, description="Name of the vaccine")
    dose_number: int = Field(1, ge=1, description="Dose serial number")
    vaccination_date: date = Field(..., description="Date administered")
    next_due_date: date | None = Field(None, description="Next due date for booster")
    hospital: str | None = Field(
        None, max_length=100, description="Administered hospital"
    )
    doctor: str | None = Field(None, max_length=100, description="Administered doctor")
    remarks: str | None = Field(None, description="Optional remarks")


class VaccinationCreate(VaccinationBase):
    pass


class VaccinationResponse(VaccinationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    medical_record_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# Medical Record Schemas
# ==========================================
class StudentMedicalRecordBase(BaseModel):
    blood_group: BloodGroup | None = Field(None, description="Student blood group")
    height_cm: float | None = Field(None, gt=0, description="Height in centimeters")
    weight_kg: float | None = Field(None, gt=0, description="Weight in kilograms")

    vision_left: str | None = Field(
        None, max_length=10, description="Left eye vision metrics"
    )
    vision_right: str | None = Field(
        None, max_length=10, description="Right eye vision metrics"
    )
    hearing_status: str | None = Field(
        None, max_length=50, description="Hearing metric summary"
    )

    medical_conditions: str | None = Field(
        None, description="Registered medical conditions list"
    )
    chronic_diseases: str | None = Field(None, description="Chronic diseases list")
    current_medications: str | None = Field(
        None, description="Active medication routines"
    )

    doctor_name: str | None = Field(
        None, max_length=100, description="Family/primary care doctor name"
    )
    hospital_name: str | None = Field(
        None, max_length=100, description="Primary hospital care facility"
    )
    doctor_phone: str | None = Field(
        None, max_length=20, description="Doctor E.164 phone number"
    )

    insurance_provider: str | None = Field(
        None, max_length=100, description="Insurance provider name"
    )
    insurance_policy_number: str | None = Field(
        None, max_length=100, description="Insurance policy number"
    )
    medical_notes: str | None = Field(None, description="General health notations")

    is_fit_for_school: bool = Field(
        True, description="Indicating if physically fit for school activities"
    )

    last_medical_checkup: date | None = Field(None, description="Date of last checkup")
    next_medical_checkup: date | None = Field(None, description="Date of next checkup")


class StudentMedicalRecordCreate(StudentMedicalRecordBase):
    pass


class StudentMedicalRecordUpdate(StudentMedicalRecordBase):
    pass


class StudentMedicalRecordResponse(StudentMedicalRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    bmi: float | None = None
    created_at: datetime
    updated_at: datetime
    allergies: list[AllergyResponse] = []
    vaccinations: list[VaccinationResponse] = []
