from app.modules.class_subject_mapping.exceptions import (
    InvalidClassSubjectMappingException,
)


def validate_class_subject_mapping_data(
    weekly_periods: int | None,
    theory_periods: int | None,
    practical_periods: int | None,
    credits_val: float | None,
) -> None:
    """Verifies all academic parameters, periods, and credit configurations for class-subject mapping."""
    if weekly_periods is not None and weekly_periods <= 0:
        raise InvalidClassSubjectMappingException(
            "Weekly Periods must be greater than 0."
        )

    if theory_periods is not None and theory_periods < 0:
        raise InvalidClassSubjectMappingException(
            "Theory Periods must be greater than or equal to 0."
        )

    if practical_periods is not None and practical_periods < 0:
        raise InvalidClassSubjectMappingException(
            "Practical Periods must be greater than or equal to 0."
        )

    if credits_val is not None and credits_val < 0.0:
        raise InvalidClassSubjectMappingException(
            "Credits must be greater than or equal to 0."
        )

    # Theory + Practical <= Weekly Periods
    th = theory_periods if theory_periods is not None else 0
    pr = practical_periods if practical_periods is not None else 0
    wk = weekly_periods if weekly_periods is not None else 0
    if th + pr > wk:
        raise InvalidClassSubjectMappingException(
            "Sum of Theory Periods and Practical Periods cannot exceed Weekly Periods."
        )
