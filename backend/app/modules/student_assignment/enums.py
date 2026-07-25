from enum import Enum


class AssignmentStatus(str, Enum):
    """Enumeration representing student assignment statuses."""

    ACTIVE = "ACTIVE"
    TRANSFERRED = "TRANSFERRED"
    PROMOTED = "PROMOTED"
    GRADUATED = "GRADUATED"
    LEFT = "LEFT"
