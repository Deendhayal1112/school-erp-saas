from datetime import date

from app.modules.term.exceptions import InvalidTermDataException


def validate_dates(start_date: date, end_date: date) -> None:
    """Verifies that the end date is strictly greater than the start date."""
    if end_date <= start_date:
        raise InvalidTermDataException("End Date must be greater than Start Date.")


def validate_containment(
    term_start: date, term_end: date, ay_start: date, ay_end: date
) -> None:
    """Verifies that the term dates fall completely within the academic year dates."""
    if term_start < ay_start or term_end > ay_end:
        raise InvalidTermDataException(
            f"Term dates ({term_start} to {term_end}) must fall completely inside "
            f"Academic Year dates ({ay_start} to {ay_end})."
        )
