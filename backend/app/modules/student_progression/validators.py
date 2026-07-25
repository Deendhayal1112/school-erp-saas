import uuid

from app.modules.student_progression.exceptions import InvalidProgressionDataException

_ACADEMIC_YEARS_ORDER: list[uuid.UUID] = []
_FINAL_CLASS_ID: uuid.UUID | None = None


def register_progression_metadata(
    academic_years_order: list[uuid.UUID],
    final_class_id: uuid.UUID,
) -> None:
    """Registers metadata contexts for progression and graduation rules verification."""
    global _FINAL_CLASS_ID
    _ACADEMIC_YEARS_ORDER.clear()
    _ACADEMIC_YEARS_ORDER.extend(academic_years_order)
    _FINAL_CLASS_ID = final_class_id


def clear_progression_metadata() -> None:
    """Utility to clear registered metadata contexts."""
    global _FINAL_CLASS_ID
    _ACADEMIC_YEARS_ORDER.clear()
    _FINAL_CLASS_ID = None


def validate_promotion_sequence(from_year_id: uuid.UUID, to_year_id: uuid.UUID) -> None:
    """Validates that promotion is allowed only to the immediate next academic year."""
    if not _ACADEMIC_YEARS_ORDER:
        return

    if from_year_id not in _ACADEMIC_YEARS_ORDER:
        raise InvalidProgressionDataException(
            "Current academic year is not registered in sequence."
        )
    if to_year_id not in _ACADEMIC_YEARS_ORDER:
        raise InvalidProgressionDataException(
            "Target academic year is not registered in sequence."
        )

    from_idx = _ACADEMIC_YEARS_ORDER.index(from_year_id)
    to_idx = _ACADEMIC_YEARS_ORDER.index(to_year_id)

    if to_idx != from_idx + 1:
        raise InvalidProgressionDataException(
            "Student can only be promoted to the immediate next academic year."
        )


def validate_graduation_class(current_class_id: uuid.UUID) -> None:
    """Enforces that graduation is allowed only from the final registered class."""
    if _FINAL_CLASS_ID is None:
        return

    if current_class_id != _FINAL_CLASS_ID:
        raise InvalidProgressionDataException(
            "Graduation is allowed only from the final class."
        )
