import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.security import mask_sensitive_value
from app.modules.employee.enums import (
    BloodGroup,
    EmployeeType,
    EmploymentStatus,
    MaritalStatus,
    SalaryType,
)


class EmployeeBase(BaseModel):
    department_id: uuid.UUID
    designation_id: uuid.UUID
    employee_number: str = Field(..., max_length=50)
    employee_type: EmployeeType
    employment_status: EmploymentStatus = EmploymentStatus.PROBATION
    joining_date: date
    confirmation_date: date | None = None
    first_name: str = Field(..., max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., max_length=100)
    gender: str = Field(..., max_length=20)
    date_of_birth: date
    blood_group: BloodGroup | None = None
    marital_status: MaritalStatus | None = None
    nationality: str = Field("Indian", max_length=50)
    email: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=20)
    alternate_phone: str | None = Field(None, max_length=20)
    emergency_contact_name: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, max_length=20)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field("India", max_length=100)
    profile_photo_url: str | None = Field(None, max_length=255)
    bank_name: str | None = Field(None, max_length=100)
    ifsc_code: str | None = Field(None, max_length=20)
    salary_type: SalaryType = SalaryType.MONTHLY
    basic_salary: float = Field(0.0, ge=0.0)
    currency: str = Field("INR", max_length=10)


class EmployeeCreate(EmployeeBase):
    aadhaar_number: str | None = Field(None, max_length=50)
    pan_number: str | None = Field(None, max_length=50)
    passport_number: str | None = Field(None, max_length=50)
    bank_account_number: str | None = Field(None, max_length=50)


class EmployeeUpdate(BaseModel):
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employment_status: EmploymentStatus | None = None
    confirmation_date: date | None = None
    first_name: str | None = Field(None, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    gender: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None
    blood_group: BloodGroup | None = None
    marital_status: MaritalStatus | None = None
    nationality: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    alternate_phone: str | None = Field(None, max_length=20)
    emergency_contact_name: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, max_length=20)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)
    profile_photo_url: str | None = Field(None, max_length=255)
    aadhaar_number: str | None = Field(None, max_length=50)
    pan_number: str | None = Field(None, max_length=50)
    passport_number: str | None = Field(None, max_length=50)
    bank_name: str | None = Field(None, max_length=100)
    bank_account_number: str | None = Field(None, max_length=50)
    ifsc_code: str | None = Field(None, max_length=20)
    salary_type: SalaryType | None = None
    basic_salary: float | None = Field(None, ge=0.0)
    currency: str | None = Field(None, max_length=10)


class EmployeeResponse(EmployeeBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    is_locked: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    # Masked fields in response representation
    aadhaar_number: str | None
    pan_number: str | None
    passport_number: str | None
    bank_account_number: str | None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("aadhaar_number")
    def serialize_aadhaar(self, v: str | None) -> str | None:
        return mask_sensitive_value(v)

    @field_serializer("pan_number")
    def serialize_pan(self, v: str | None) -> str | None:
        return mask_sensitive_value(v)

    @field_serializer("passport_number")
    def serialize_passport(self, v: str | None) -> str | None:
        return mask_sensitive_value(v)

    @field_serializer("bank_account_number")
    def serialize_bank(self, v: str | None) -> str | None:
        return mask_sensitive_value(v)
