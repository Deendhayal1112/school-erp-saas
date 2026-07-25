"""
Platform Error Codes.
"""

from enum import Enum


class ErrorCode(str, Enum):
    """Categorized taxonomic error codes returning unified platform feedback."""
    SYSTEM_ERROR = "SYS_001"
    VALIDATION_ERROR = "ValidationError"
    NOT_FOUND = "ERR_404"
    BAD_REQUEST = "ERR_400"
    UNAUTHORIZED = "ERR_401"
    FORBIDDEN = "ERR_403"
    CONFLICT = "ERR_409"
    RATE_LIMIT_EXCEEDED = "ERR_429"
    DATABASE_ERROR = "DB_001"
