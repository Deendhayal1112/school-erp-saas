import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CurrentUserResponse(BaseModel):
    """Schema representing profile metadata returned to the currently authenticated user."""
    id: uuid.UUID = Field(
        ...,
        description="The unique user identifier (UUID).",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    school_id: uuid.UUID = Field(
        ...,
        description="The associated School tenant ID.",
        examples=["987f6543-e21b-34d5-c678-987654321000"],
    )
    email: str = Field(
        ...,
        description="The registered email address associated with the user.",
        examples=["teacher@demoschool.edu"],
    )
    full_name: str = Field(
        ...,
        description="The computed full name representing first_name + last_name.",
        examples=["John Doe"],
    )
    role: str = Field(
        ...,
        description="The unique code mapping the authorization role profile.",
        examples=["TEACHER"],
    )
    is_active: bool = Field(
        ...,
        description="Indicates whether the account active status is toggled.",
        examples=[True],
    )
    created_at: datetime = Field(
        ...,
        description="Account audit record creation timestamp.",
        examples=["2026-07-25T09:00:00Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="Account audit record last update timestamp.",
        examples=["2026-07-25T09:00:00Z"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "school_id": "987f6543-e21b-34d5-c678-987654321000",
                "email": "teacher@demoschool.edu",
                "full_name": "John Doe",
                "role": "TEACHER",
                "is_active": True,
                "created_at": "2026-07-25T09:00:00Z",
                "updated_at": "2026-07-25T09:00:00Z",
            }
        }
    }
