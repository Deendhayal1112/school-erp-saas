from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standardized wrapper envelope for all successful API operations."""

    success: bool = Field(True, description="Indicates operation completed successfully.")
    message: str = Field("Operation successful", description="A short, readable status message.")
    data: T | None = Field(None, description="The primary return payload data (optional).")


class ErrorResponse(BaseModel):
    """Standardized wrapper envelope for all business or runtime errors."""

    success: bool = Field(False, description="Indicates operation failed.")
    error: str = Field(..., description="Machine-readable error code classification.")
    message: str = Field(..., description="Human-readable error details description.")


class ValidationErrorDetail(BaseModel):
    """Specific schema detail for a single input validation parameter failure."""

    loc: list[str] = Field(..., description="Field path location of the validation error.")
    msg: str = Field(..., description="Error validation description message.")
    type: str = Field(..., description="Validation rules type tag description.")


class ValidationErrorResponse(BaseModel):
    """Standardized wrapper envelope returned on HTTP 422 input parameter errors."""

    success: bool = Field(False, description="Indicates operation failed.")
    error: str = Field("ValidationError", description="Validation error classification code.")
    message: str = Field("Input validation checks failed", description="Summary description.")
    details: list[ValidationErrorDetail] = Field(
        ..., description="Complete list of fields that violated schema rules."
    )
