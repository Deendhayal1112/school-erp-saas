import re
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """Schema representing credentials sent to authenticate a login session."""
    email: str = Field(
        ...,
        description="Standard email login identifier. Whitespace will be trimmed.",
        examples=["admin@demoschool.edu"],
    )
    password: str = Field(
        ...,
        description="The plaintext password credentials associated with the user account.",
        examples=["Password123!"],
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

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforces a minimum password length restriction on submitted logins."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class LoginResponse(BaseModel):
    """Schema representing the standard successful authentication response payload."""
    access_token: str = Field(
        ...,
        description="JSON Web Access Token used to authenticate requesting API headers.",
    )
    refresh_token: str = Field(
        ...,
        description="JSON Web Refresh Token used to rotate expiring Access Tokens.",
    )
    token_type: str = Field(
        "bearer",
        description="The authorization header transport token classification scheme.",
        examples=["bearer"],
    )
    expires_in: int = Field(
        ...,
        description="The lifespan duration of the Access Token in seconds.",
        examples=[1800],
    )
