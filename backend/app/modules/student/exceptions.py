from typing import Any

from app.exceptions.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)


class StudentNotFoundException(NotFoundException):
    """Raised when the requested student is not found."""
    def __init__(self, message: str = "Student not found", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class DuplicateAdmissionNumberException(ConflictException):
    """Raised when the admission number is already in use within the school."""
    def __init__(self, message: str = "Admission number already registered in this school", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class DuplicateEmailException(ConflictException):
    """Raised when the student email is already registered."""
    def __init__(self, message: str = "Student email already registered", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class InvalidAgeException(BadRequestException):
    """Raised when the student's age is outside of allowed limits."""
    def __init__(self, message: str = "Student age must be between 2 and 30 years old", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class InvalidAdmissionDateException(BadRequestException):
    """Raised when the joined/admission date is invalid (e.g. in the future or after graduation date)."""
    def __init__(self, message: str = "Invalid joined or graduation date", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class StudentAlreadyExistsException(ConflictException):
    """Raised when creating a student that already exists in the tenant context."""
    def __init__(self, message: str = "Student record already exists", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
