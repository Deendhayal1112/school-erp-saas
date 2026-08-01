"""
Exceptions for the Timetable Dashboard, Analytics & Reports module.
"""

from app.exceptions.exceptions import BadRequestException


class TimetableDashboardException(BadRequestException):
    """Base exception class for timetable dashboard operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message)
