from datetime import date

from app.modules.curriculum.exceptions import InvalidCurriculumException


def validate_curriculum_data(
    curriculum_code: str | None,
    curriculum_name: str | None,
    completion_percentage: float | None,
    estimated_hours: int | None,
    effective_from: date | None,
    effective_to: date | None,
) -> None:
    """Verifies all academic parameters, duration metrics, and date ranges for curriculum configurations."""
    # 1. Curriculum Code required
    if curriculum_code is not None and not curriculum_code.strip():
        raise InvalidCurriculumException(
            "Curriculum Code is required and cannot be empty."
        )

    # 2. Curriculum Name required
    if curriculum_name is not None and not curriculum_name.strip():
        raise InvalidCurriculumException(
            "Curriculum Name is required and cannot be empty."
        )

    # 3. Completion Percentage: 0-100
    if completion_percentage is not None:
        if completion_percentage < 0.0 or completion_percentage > 100.0:
            raise InvalidCurriculumException(
                "Completion Percentage must be between 0 and 100."
            )

    # 4. Estimated Hours > 0
    if estimated_hours is not None and estimated_hours <= 0:
        raise InvalidCurriculumException("Estimated Hours must be greater than 0.")

    # 5. Effective From <= Effective To
    if effective_from is not None and effective_to is not None:
        if effective_from > effective_to:
            raise InvalidCurriculumException(
                "Effective From date cannot be after Effective To date."
            )
