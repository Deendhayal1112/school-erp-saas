"""
Validators for the Timetable Dashboard, Analytics & Reports module.
"""

from datetime import date

from app.modules.timetable_dashboard.constants import SUPPORTED_EXPORT_FORMATS
from app.modules.timetable_dashboard.exceptions import TimetableDashboardException


def validate_export_format(format_name: str) -> None:
    """Verifies that the requested file export format is supported."""
    if format_name.lower() not in SUPPORTED_EXPORT_FORMATS:
        raise TimetableDashboardException(
            f"Unsupported export format '{format_name}'. Supported formats: {list(SUPPORTED_EXPORT_FORMATS)}."
        )


def validate_date_range(date_from: date | None, date_to: date | None) -> None:
    """Verifies date ordering constraints."""
    if date_from and date_to and date_from > date_to:
        raise TimetableDashboardException(
            "Start date (date_from) cannot be after end date (date_to)."
        )
