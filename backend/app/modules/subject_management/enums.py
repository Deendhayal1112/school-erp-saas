from enum import Enum


class SubjectType(str, Enum):
    CORE = "CORE"
    ELECTIVE = "ELECTIVE"
    OPTIONAL = "OPTIONAL"
    LANGUAGE = "LANGUAGE"
    LAB = "LAB"
    ACTIVITY = "ACTIVITY"


class SubjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
