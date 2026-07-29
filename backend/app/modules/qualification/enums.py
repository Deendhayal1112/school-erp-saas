import enum


class QualificationType(str, enum.Enum):
    SECONDARY = "SECONDARY"
    HIGHER_SECONDARY = "HIGHER_SECONDARY"
    GRADUATION = "GRADUATION"
    POST_GRADUATION = "POST_GRADUATION"
    DOCTORATE = "DOCTORATE"
    DIPLOMA = "DIPLOMA"
    CERTIFICATION = "CERTIFICATION"
    OTHER = "OTHER"


class ModeOfStudy(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    DISTANCE = "DISTANCE"
    ONLINE = "ONLINE"


class QualificationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
