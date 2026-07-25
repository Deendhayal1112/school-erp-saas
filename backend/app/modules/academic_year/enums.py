from enum import Enum


class AcademicYearStatus(str, Enum):
    """
    Status of an Academic Year.
    """

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
