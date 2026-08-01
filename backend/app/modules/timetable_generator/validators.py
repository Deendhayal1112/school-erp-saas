import uuid

from app.exceptions.exceptions import BadRequestException


def validate_generation_params(
    school_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    term_id: uuid.UUID,
) -> None:
    """Validates the input parameters for automatic timetable generation."""
    if not school_id or not academic_year_id or not term_id:
        raise BadRequestException(message="School ID, Academic Year ID, and Term ID are required.")
