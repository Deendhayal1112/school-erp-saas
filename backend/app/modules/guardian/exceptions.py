from typing import Any

from app.exceptions.exceptions import ConflictException, NotFoundException


class GuardianNotFoundException(NotFoundException):
    """Raised when the requested guardian is not found."""

    def __init__(
        self, message: str = "Guardian not found", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, details)


class DuplicateGuardianPhoneException(ConflictException):
    """Raised when the guardian phone is already in use within the school."""

    def __init__(
        self,
        message: str = "Guardian phone number already registered in this school",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class DuplicateGuardianEmailException(ConflictException):
    """Raised when the guardian email is already registered within the school."""

    def __init__(
        self,
        message: str = "Guardian email address already registered in this school",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class DuplicateGuardianAadhaarException(ConflictException):
    """Raised when the guardian Aadhaar number is already registered within the school."""

    def __init__(
        self,
        message: str = "Guardian Aadhaar number already registered in this school",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
