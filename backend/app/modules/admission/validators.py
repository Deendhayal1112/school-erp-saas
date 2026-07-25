import re
from datetime import date

from app.exceptions.exceptions import BadRequestException


def validate_academic_year(value: str) -> str:
    """Validates academic year matches YYYY-YYYY pattern and has a logical range."""
    value = value.strip()
    match = re.match(r"^(\d{4})-(\d{4})$", value)
    if not match:
        raise ValueError(
            "Academic year must follow the YYYY-YYYY format (e.g., 2026-2027)."
        )

    start_year = int(match.group(1))
    end_year = int(match.group(2))

    if end_year != start_year + 1:
        raise ValueError(
            "Academic year end year must be start year + 1 (e.g., 2026-2027)."
        )

    return value


def validate_admission_dates(
    application_date: date, admission_date: date | None
) -> None:
    """Verifies that admission date is not prior to the application submission date."""
    if admission_date and admission_date < application_date:
        raise BadRequestException(
            "Admission date cannot be set before the application date."
        )
