"""
Email Verification Schemas.
"""

import re

from pydantic import BaseModel, Field, field_validator


class VerifyEmailRequest(BaseModel):
    """Schema representing validation parameters to complete email verification."""

    token: str = Field(
        ...,
        description="The cryptographic validation token received in the verification email.",
    )


class ResendVerificationRequest(BaseModel):
    """Schema representing email parameter needed to resend a verification token."""

    email: str = Field(
        ...,
        description="The registered email address associated with the account.",
        examples=["admin@demoschool.edu"],
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Enforces whitespace trimming and standard email regex validation."""
        v = v.strip()
        regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(regex, v):
            raise ValueError("Invalid email format.")
        return v
