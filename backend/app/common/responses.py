"""
Unified API Response Models.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.schemas.response import (
    ErrorResponse,
    SuccessResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)

T = TypeVar("T")


class PaginationMetadata(BaseModel):
    """Metadata enclosing details for paginated record queries."""
    total_records: int = Field(..., description="Total count of database records matching the filter criteria.")
    page: int = Field(..., description="Active requested page index (1-indexed).")
    page_size: int = Field(..., description="Count limit of records returned per query page.")
    total_pages: int = Field(..., description="Calculated count of available result pages.")
    next: str | None = Field(None, description="Request URI path reference to pull the subsequent page payload.")
    previous: str | None = Field(None, description="Request URI path reference to pull the preceding page payload.")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized wrapper envelope for paginated result listings."""
    success: bool = Field(True, description="Indicates operation completed successfully.")
    message: str = Field("Query completed successfully", description="Status message description.")
    pagination: PaginationMetadata = Field(..., description="Query pagination offsets and total count references.")
    results: list[T] = Field(..., description="The query payload results slice.")


class CreatedResponse(SuccessResponse[T]):
    """Default envelope helper representing resource creation completed successfully (HTTP 201)."""
    message: str = Field("Resource created successfully", description="Status message.")


class UpdatedResponse(SuccessResponse[T]):
    """Default envelope helper representing resource modifications successfully completed (HTTP 200)."""
    message: str = Field("Resource updated successfully", description="Status message.")


class DeletedResponse(BaseModel):
    """Default envelope helper representing resource deletion successfully completed (HTTP 200)."""
    success: bool = Field(True, description="Indicates operation completed successfully.")
    message: str = Field("Resource deleted successfully", description="Status message.")
    data: Any | None = Field(None, description="Empty data payload descriptor.")


__all__ = [
    "SuccessResponse",
    "ErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    "PaginationMetadata",
    "PaginatedResponse",
    "CreatedResponse",
    "UpdatedResponse",
    "DeletedResponse",
]
