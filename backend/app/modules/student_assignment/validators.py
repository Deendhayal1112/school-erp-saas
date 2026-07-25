import uuid

from app.modules.student_assignment.exceptions import InvalidAssignmentDataException

# Registries for mock academic master configurations
_MOCK_ACADEMIC_YEARS: set[uuid.UUID] = set()
_MOCK_CLASSES: set[uuid.UUID] = set()
_MOCK_SECTIONS: dict[uuid.UUID, uuid.UUID] = {}  # maps section_id -> class_id


def register_mock_metadata(
    academic_years: list[uuid.UUID],
    classes: list[uuid.UUID],
    sections: dict[uuid.UUID, uuid.UUID],
) -> None:
    """Utility to register mock master metadata contexts for testing verification."""
    _MOCK_ACADEMIC_YEARS.update(academic_years)
    _MOCK_CLASSES.update(classes)
    _MOCK_SECTIONS.update(sections)


def clear_mock_metadata() -> None:
    """Clears registered mock configuration registry."""
    _MOCK_ACADEMIC_YEARS.clear()
    _MOCK_CLASSES.clear()
    _MOCK_SECTIONS.clear()


def validate_academic_metadata(
    academic_year_id: uuid.UUID,
    class_id: uuid.UUID,
    section_id: uuid.UUID | None = None,
) -> None:
    """Verifies academic metadata configuration alignments."""
    # If no mock metadata is registered, skip validation checks to allow standard runs
    if not _MOCK_ACADEMIC_YEARS and not _MOCK_CLASSES:
        return

    if academic_year_id not in _MOCK_ACADEMIC_YEARS:
        raise InvalidAssignmentDataException("Academic Year must exist.")

    if class_id not in _MOCK_CLASSES:
        raise InvalidAssignmentDataException("Class must exist.")

    if section_id is not None:
        if section_id not in _MOCK_SECTIONS:
            raise InvalidAssignmentDataException("Section must exist.")
        if _MOCK_SECTIONS[section_id] != class_id:
            raise InvalidAssignmentDataException("Section must belong to Class.")
