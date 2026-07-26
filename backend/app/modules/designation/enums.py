from enum import Enum


class DesignationStatus(str, Enum):
    """Enumeration of designation status configurations."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
