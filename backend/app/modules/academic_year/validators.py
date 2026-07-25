from datetime import date

from app.modules.academic_year.exceptions import InvalidAcademicYearDataException


def validate_dates(start_date: date, end_date: date) -> None:
    """Verifies that the end date is strictly greater than the start date."""
    if end_date <= start_date:
        raise InvalidAcademicYearDataException(
            "End Date must be greater than Start Date."
        )
