from typing import Any

from app.exceptions.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)


class AdmissionNotFoundException(NotFoundException):
    """Raised when the requested admission record is not found."""

    def __init__(
        self,
        message: str = "Admission application not found.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class InvalidAdmissionTransitionException(ConflictException):
    """Raised when attempting an invalid stage transition in the workflow."""

    def __init__(
        self,
        message: str = "Invalid workflow status transition.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class DuplicateAdmissionApplicationException(ConflictException):
    """Raised when the student already has a pending or completed admission application."""

    def __init__(
        self,
        message: str = "Active admission application or enrollment already exists for this student.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class StudentGuardianRequiredException(BadRequestException):
    """Raised when validating an admission application without linked guardians."""

    def __init__(
        self,
        message: str = "Admission requires the student to have at least one registered guardian mapping.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
