from enum import StrEnum


class GenderRestriction(StrEnum):
    ALL = "ALL"
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class LeaveStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class LeaveRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class HolidayType(StrEnum):
    PUBLIC = "PUBLIC"
    ACADEMIC = "ACADEMIC"
    REGIONAL = "REGIONAL"
    OTHER = "OTHER"


class HalfDaySession(StrEnum):
    FIRST_HALF = "FIRST_HALF"
    SECOND_HALF = "SECOND_HALF"
