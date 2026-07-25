import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.guardian.enums import Relationship
from app.modules.guardian.validators import (
    validate_aadhaar_number,
    validate_guardian_phone,
)


class GuardianBase(BaseModel):
    first_name: str = Field(
        ..., min_length=1, max_length=50, description="First name of the guardian."
    )
    middle_name: str | None = Field(
        None, max_length=50, description="Optional middle name of the guardian."
    )
    last_name: str = Field(
        ..., min_length=1, max_length=50, description="Last name of the guardian."
    )
    relationship: Relationship = Field(
        ..., description="Default relationship type of the guardian."
    )

    occupation: str | None = Field(
        None, max_length=100, description="Guardian's occupation."
    )
    qualification: str | None = Field(
        None, max_length=100, description="Guardian's educational qualification."
    )
    annual_income: float | None = Field(None, description="Guardian's annual income.")

    email: str | None = Field(
        None, max_length=100, description="Contact email address."
    )
    phone: str = Field(
        ..., max_length=20, description="Primary contact phone (E.164 format)."
    )
    alternate_phone: str | None = Field(
        None, max_length=20, description="Alternate contact phone (E.164 format)."
    )
    aadhaar_number: str | None = Field(
        None, max_length=12, description="12-digit Aadhaar card number."
    )

    address: str | None = Field(None, max_length=255, description="Street address.")
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field("India", max_length=100)
    postal_code: str | None = Field(None, max_length=20)

    is_primary_guardian: bool = Field(
        False, description="Flag indicating if this is a primary guardian."
    )
    is_emergency_contact: bool = Field(
        False, description="Flag indicating if this is an emergency contact."
    )
    remarks: str | None = Field(None, description="Optional comments/remarks.")


class GuardianCreate(GuardianBase):
    school_id: uuid.UUID = Field(..., description="School tenant UUID context.")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        res = validate_guardian_phone(v)
        if not res:
            raise ValueError("Phone number is required.")
        return res

    @field_validator("alternate_phone")
    @classmethod
    def validate_alt_phone(cls, v: str | None) -> str | None:
        return validate_guardian_phone(v)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar_no(cls, v: str | None) -> str | None:
        return validate_aadhaar_number(v)

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str | None) -> str | None:
        if v is not None:
            clean = v.strip()
            if not re.match(r"^[\w\.\+\-]+@[\w\.\-]+\.\w+$", clean):
                raise ValueError("Invalid email format.")
            return clean.lower()
        return v


class GuardianUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=50)
    middle_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    relationship: Relationship | None = Field(None)

    occupation: str | None = Field(None, max_length=100)
    qualification: str | None = Field(None, max_length=100)
    annual_income: float | None = Field(None)

    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    alternate_phone: str | None = Field(None, max_length=20)
    aadhaar_number: str | None = Field(None, max_length=12)

    address: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)

    is_primary_guardian: bool | None = Field(None)
    is_emergency_contact: bool | None = Field(None)
    is_active: bool | None = Field(None)
    remarks: str | None = Field(None)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return validate_guardian_phone(v)

    @field_validator("alternate_phone")
    @classmethod
    def validate_alt_phone(cls, v: str | None) -> str | None:
        return validate_guardian_phone(v)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar_no(cls, v: str | None) -> str | None:
        return validate_aadhaar_number(v)

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str | None) -> str | None:
        if v is not None:
            clean = v.strip()
            if not re.match(r"^[\w\.\+\-]+@[\w\.\-]+\.\w+$", clean):
                raise ValueError("Invalid email format.")
            return clean.lower()
        return v


class GuardianResponse(GuardianBase):
    id: uuid.UUID
    school_id: uuid.UUID
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class StudentGuardianMappingCreate(BaseModel):
    guardian_id: uuid.UUID = Field(..., description="Mapped Guardian UUID.")
    relationship_type: Relationship = Field(
        ..., description="Mapping-specific relationship type."
    )
    is_primary_guardian: bool = Field(False)
    is_emergency_contact: bool = Field(False)
    is_pickup_authorized: bool = Field(False)


class StudentGuardianMappingUpdate(BaseModel):
    relationship_type: Relationship | None = Field(None)
    is_primary_guardian: bool | None = Field(None)
    is_emergency_contact: bool | None = Field(None)
    is_pickup_authorized: bool | None = Field(None)


class StudentGuardianMappingResponse(BaseModel):
    student_id: uuid.UUID
    guardian_id: uuid.UUID
    relationship_type: Relationship
    is_primary_guardian: bool
    is_emergency_contact: bool
    is_pickup_authorized: bool
    guardian: GuardianResponse | None = None

    model_config = ConfigDict(from_attributes=True)
