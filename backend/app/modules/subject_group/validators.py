from app.modules.subject_group.exceptions import InvalidSubjectGroupDataException


def validate_subject_group_data(
    group_name: str | None,
    group_code: str | None,
    display_name: str | None,
    display_order: int | None,
    minimum_subjects: int | None,
    maximum_subjects: int | None,
    is_core: bool | None,
    is_elective: bool | None,
) -> None:
    """Verifies all academic parameters, type dependencies, and score configurations for a subject group."""
    # 1. Group Name required.
    if group_name is not None and not group_name.strip():
        raise InvalidSubjectGroupDataException(
            "Group Name is required and cannot be empty."
        )

    # 2. Group Code required.
    if group_code is not None and not group_code.strip():
        raise InvalidSubjectGroupDataException(
            "Group Code is required and cannot be empty."
        )

    # 3. Display Name required.
    if display_name is not None and not display_name.strip():
        raise InvalidSubjectGroupDataException(
            "Display Name is required and cannot be empty."
        )

    # 4. Display Order required.
    if display_order is not None and display_order < 0:
        raise InvalidSubjectGroupDataException(
            "Display Order must be greater than or equal to 0."
        )

    # 5. Minimum Subjects >= 0.
    if minimum_subjects is not None and minimum_subjects < 0:
        raise InvalidSubjectGroupDataException(
            "Minimum Subjects must be greater than or equal to 0."
        )

    # 6. Maximum Subjects >= Minimum Subjects.
    if maximum_subjects is not None and minimum_subjects is not None:
        if maximum_subjects < minimum_subjects:
            raise InvalidSubjectGroupDataException(
                "Maximum Subjects must be greater than or equal to Minimum Subjects."
            )

    # 7. Core vs Elective logical consistency check.
    if is_core and is_elective:
        raise InvalidSubjectGroupDataException(
            "A subject group cannot be both a Core and an Elective group."
        )
