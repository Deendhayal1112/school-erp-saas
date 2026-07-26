from app.modules.subject_management.enums import SubjectType
from app.modules.subject_management.exceptions import InvalidSubjectDataException


def validate_subject_data(
    subject_code: str | None,
    subject_name: str | None,
    display_name: str | None,
    credits: float | None,
    weekly_periods: int | None,
    theory_hours: int | None,
    practical_hours: int | None,
    passing_marks: int | None,
    maximum_marks: int | None,
    display_order: int | None,
    subject_type: SubjectType | None,
    language: str | None,
    is_core: bool | None,
    is_elective: bool | None,
    has_practical: bool | None,
) -> None:
    """Verifies all academic parameters, type dependencies, and score configurations for a subject."""
    # 1. Subject Code required.
    if subject_code is not None and not subject_code.strip():
        raise InvalidSubjectDataException(
            "Subject Code is required and cannot be empty."
        )

    # 2. Subject Name required.
    if subject_name is not None and not subject_name.strip():
        raise InvalidSubjectDataException(
            "Subject Name is required and cannot be empty."
        )

    # 3. Display Name required.
    if display_name is not None and not display_name.strip():
        raise InvalidSubjectDataException(
            "Display Name is required and cannot be empty."
        )

    # 4. Credits >= 0.
    if credits is not None and credits < 0:
        raise InvalidSubjectDataException("Credits must be greater than or equal to 0.")

    # 5. Weekly Periods > 0.
    if weekly_periods is not None and weekly_periods <= 0:
        raise InvalidSubjectDataException(
            "Weekly Periods must be strictly greater than 0."
        )

    # 6. Theory Hours >= 0.
    if theory_hours is not None and theory_hours < 0:
        raise InvalidSubjectDataException(
            "Theory Hours must be greater than or equal to 0."
        )

    # 7. Practical Hours >= 0.
    if practical_hours is not None and practical_hours < 0:
        raise InvalidSubjectDataException(
            "Practical Hours must be greater than or equal to 0."
        )

    # 8. Passing Marks >= 0.
    if passing_marks is not None and passing_marks < 0:
        raise InvalidSubjectDataException(
            "Passing Marks must be greater than or equal to 0."
        )

    # 9. Maximum Marks > Passing Marks.
    if maximum_marks is not None and passing_marks is not None:
        if maximum_marks <= passing_marks:
            raise InvalidSubjectDataException(
                "Maximum Marks must be strictly greater than Passing Marks."
            )

    # 10. Display Order required.
    if display_order is not None and display_order < 0:
        raise InvalidSubjectDataException(
            "Display Order is required and must be greater than or equal to 0."
        )

    # 11. Language subjects must have language specified.
    if subject_type == SubjectType.LANGUAGE and not language:
        raise InvalidSubjectDataException(
            "Language subjects must specify the target language."
        )

    # 12. Lab subjects must have practical hours > 0.
    if (
        subject_type == SubjectType.LAB or has_practical
    ) and practical_hours is not None:
        if practical_hours <= 0:
            raise InvalidSubjectDataException(
                "Lab and practical-enabled subjects must have practical hours greater than 0."
            )

    # 13. Elective subjects cannot be Core.
    if is_core and is_elective:
        raise InvalidSubjectDataException(
            "A subject cannot be both a Core and an Elective subject."
        )

    if subject_type == SubjectType.ELECTIVE:
        if is_core:
            raise InvalidSubjectDataException(
                "Elective subject types cannot have the 'is_core' flag set to True."
            )
        if is_elective is False:
            raise InvalidSubjectDataException(
                "Elective subject types must have 'is_elective' set to True."
            )
