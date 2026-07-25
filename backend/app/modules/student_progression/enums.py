from enum import Enum


class ProgressionType(str, Enum):
    """Enumeration of student academic progression types."""

    PROMOTION = "PROMOTION"
    TRANSFER = "TRANSFER"
    GRADUATION = "GRADUATION"
    ALUMNI = "ALUMNI"
    REPEAT_CLASS = "REPEAT_CLASS"
    WITHDRAWAL = "WITHDRAWAL"
