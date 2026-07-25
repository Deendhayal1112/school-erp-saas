"""
Base Custom Exception.
"""

from typing import Any

from app.exceptions.error_codes import ErrorCode


class PlatformException(Exception):
    """Base exception indicating business logic or platform verification failures."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.SYSTEM_ERROR,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
