"""
Specific platform exceptions.
"""

from typing import Any

from app.exceptions.base import PlatformException
from app.exceptions.error_codes import ErrorCode


class NotFoundException(PlatformException):
    """Raised when request target resource is not found in persistent databases."""

    def __init__(
        self, message: str = "Resource not found", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, ErrorCode.NOT_FOUND, 404, details)


class BadRequestException(PlatformException):
    """Raised when client parameters violate format constraints or operational sanity."""

    def __init__(
        self,
        message: str = "Bad request parameter",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, ErrorCode.BAD_REQUEST, 400, details)


class UnauthorizedException(PlatformException):
    """Raised when credential verification or session signature fails validation."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, ErrorCode.UNAUTHORIZED, 401, details)


class ForbiddenException(PlatformException):
    """Raised when authenticated user permissions are insufficient for requested action."""

    def __init__(
        self, message: str = "Action forbidden", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, ErrorCode.FORBIDDEN, 403, details)


class ConflictException(PlatformException):
    """Raised when mutative operation conflicts with existing system state (e.g. key collision)."""

    def __init__(
        self,
        message: str = "Resource state conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, ErrorCode.CONFLICT, 409, details)


class RateLimitExceededException(PlatformException):
    """Raised when client API call volume exceeds request quota configuration."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, ErrorCode.RATE_LIMIT_EXCEEDED, 429, details)
