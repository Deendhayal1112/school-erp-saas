import re

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.password import validate_password_strength


class ChangePasswordRequest(BaseModel):
    """Schema representing credentials sent to change a user's password."""

    current_password: str = Field(
        ...,
        description="The active plaintext password credential associated with the session.",
        examples=["OldPassword123!"],
    )
    new_password: str = Field(
        ...,
        description="The requested plaintext new password complying with security complexity checks.",
        examples=["NewSecurePassword123!"],
    )
    confirm_password: str = Field(
        ...,
        description="Must be identical to the requested new_password value.",
        examples=["NewSecurePassword123!"],
    )

    @field_validator("new_password")
    @classmethod
    def check_new_password_strength(cls, v: str) -> str:
        """Enforces complexity strength checks on the requested new password."""
        validate_password_strength(v)
        return v

    @model_validator(mode="after")
    def verify_passwords_match(self) -> "ChangePasswordRequest":
        """Ensures the confirm password matches and is different from the current password."""
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm password do not match.")
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password.")
        return self


class ForgotPasswordRequest(BaseModel):
    """Schema representing parameters required to request a password reset email."""

    email: str = Field(
        ...,
        description="The registered email address associated with the account.",
        examples=["admin@demoschool.edu"],
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Enforces whitespace trimming and checks standard RFC email formats."""
        v = v.strip()
        regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(regex, v):
            raise ValueError("Invalid email format.")
        return v


class ResetPasswordRequest(BaseModel):
    """Schema representing variables required to finalize a password recovery cycle."""

    reset_token: str = Field(
        ...,
        description="The cryptographic validation token received in the password recovery email.",
    )
    new_password: str = Field(
        ...,
        description="The requested new password.",
        examples=["NewSecurePassword123!"],
    )
    confirm_password: str = Field(
        ...,
        description="Must be identical to the requested new_password value.",
        examples=["NewSecurePassword123!"],
    )

    @field_validator("new_password")
    @classmethod
    def check_new_password_strength(cls, v: str) -> str:
        """Enforces complexity strength checks on the requested new password."""
        validate_password_strength(v)
        return v

    @model_validator(mode="after")
    def verify_passwords_match(self) -> "ResetPasswordRequest":
        """Ensures the confirm password matches."""
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm password do not match.")
        return self
