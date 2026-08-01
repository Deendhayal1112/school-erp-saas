from enum import Enum


class TimetableStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class LessonType(str, Enum):
    THEORY = "THEORY"
    PRACTICAL = "PRACTICAL"
    LAB = "LAB"
    SEMINAR = "SEMINAR"
    TUTORIAL = "TUTORIAL"
