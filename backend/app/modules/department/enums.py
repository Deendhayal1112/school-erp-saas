from enum import Enum


class DepartmentStatus(str, Enum):
    """Enumeration of department status configurations."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
