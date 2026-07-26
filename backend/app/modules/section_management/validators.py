from app.modules.section_management.exceptions import InvalidSectionDataException


def validate_capacity(capacity: int) -> None:
    """Verifies that the capacity is strictly positive (> 0)."""
    if capacity <= 0:
        raise InvalidSectionDataException("Capacity must be greater than 0.")
