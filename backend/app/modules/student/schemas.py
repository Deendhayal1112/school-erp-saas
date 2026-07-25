import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.student.enums import Gender, StudentStatus
from app.modules.student.validators import (
    validate_aadhaar,
    validate_student_dob,
    validate_student_email,
    validate_student_phone,
)


class StudentBase(BaseModel):
    admission_number: str = Field(..., max_length=50, description="Admission number unique within the school.")
    roll_number: str | None = Field(None, max_length=50, description="Roll number inside class/section.")
    emis_number: str | None = Field(None, max_length=50, description="Optional EMIS tracking number.")

    first_name: str = Field(..., min_length=1, max_length=50, description="First name of the student.")
    middle_name: str | None = Field(None, max_length=50, description="Optional middle name of the student.")
    last_name: str = Field(..., min_length=1, max_length=50, description="Last name of the student.")

    gender: Gender = Field(..., description="Recognized gender of the student.")
    date_of_birth: date = Field(..., description="Date of birth of the student.")
    blood_group: str | None = Field(None, max_length=10, description="Blood group code (e.g. A+, O-).")

    email: str | None = Field(None, max_length=100, description="Contact email of the student.")
    phone: str | None = Field(None, max_length=20, description="Contact phone of the student.")
    aadhaar_number: str | None = Field(None, max_length=12, description="Aadhaar ID number (exactly 12 digits).")

    nationality: str = Field("Indian", max_length=50)
    religion: str | None = Field(None, max_length=50)
    caste: str | None = Field(None, max_length=50)
    community: str | None = Field(None, max_length=50)
    mother_tongue: str | None = Field(None, max_length=50)

    photo_url: str | None = Field(None, max_length=255)
    joined_date: date = Field(..., description="Date student admitted into the school.")
    graduation_date: date | None = Field(None, description="Optional graduation date.")
    remarks: str | None = Field(None, description="Optional remarks.")


class StudentCreate(StudentBase):
    school_id: uuid.UUID = Field(..., description="Target School UUID context.")

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        return validate_student_dob(v)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return validate_student_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return validate_student_email(v)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar_no(cls, v: str | None) -> str | None:
        return validate_aadhaar(v)


class StudentUpdate(BaseModel):
    admission_number: str | None = Field(None, max_length=50)
    roll_number: str | None = Field(None, max_length=50)
    emis_number: str | None = Field(None, max_length=50)

    first_name: str | None = Field(None, min_length=1, max_length=50)
    middle_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)

    gender: Gender | None = Field(None)
    date_of_birth: date | None = Field(None)
    blood_group: str | None = Field(None, max_length=10)

    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    aadhaar_number: str | None = Field(None, max_length=12)

    nationality: str | None = Field(None, max_length=50)
    religion: str | None = Field(None, max_length=50)
    caste: str | None = Field(None, max_length=50)
    community: str | None = Field(None, max_length=50)
    mother_tongue: str | None = Field(None, max_length=50)

    photo_url: str | None = Field(None, max_length=255)
    joined_date: date | None = Field(None)
    graduation_date: date | None = Field(None)
    status: StudentStatus | None = Field(None)
    is_active: bool | None = Field(None)
    remarks: str | None = Field(None)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date | None) -> date | None:
        if v is not None:
            return validate_student_dob(v)
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return validate_student_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return validate_student_email(v)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar_no(cls, v: str | None) -> str | None:
        return validate_aadhaar(v)


class StudentResponse(StudentBase):
    id: uuid.UUID
    school_id: uuid.UUID
    status: StudentStatus
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class StudentSummary(BaseModel):
    id: uuid.UUID
    admission_number: str
    roll_number: str | None
    first_name: str
    last_name: str
    full_name: str
    status: StudentStatus
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StudentSearch(BaseModel):
    query: str | None = Field(None, description="Search query string.")


class StudentFilter(BaseModel):
    status: StudentStatus | None = Field(None)
    gender: Gender | None = Field(None)
    is_active: bool | None = Field(None)
    joined_date_from: date | None = Field(None)
    joined_date_to: date | None = Field(None)


class StudentListResponse(BaseModel):
    students: list[StudentSummary]
    total: int
