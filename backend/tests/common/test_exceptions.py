"""
Tests for Custom Platform Exceptions.
"""

from app.exceptions.error_codes import ErrorCode
from app.exceptions.exceptions import (
    BadRequestException,
    NotFoundException,
    RateLimitExceededException,
)


def test_exception_status_and_error_codes():
    # NotFoundException
    nfe = NotFoundException("User not found")
    assert nfe.status_code == 404
    assert nfe.error_code == ErrorCode.NOT_FOUND
    assert nfe.message == "User not found"

    # BadRequestException
    bre = BadRequestException("Invalid payload")
    assert bre.status_code == 400
    assert bre.error_code == ErrorCode.BAD_REQUEST

    # RateLimitExceededException
    rle = RateLimitExceededException()
    assert rle.status_code == 429
    assert rle.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
