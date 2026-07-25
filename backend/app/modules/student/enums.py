from enum import Enum


class Gender(str, Enum):
    """Enumeration representing the student's legal or recognized gender."""
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class StudentStatus(str, Enum):
    """Enumeration representing the enrollment and administrative status of a student."""
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    TRANSFERRED = "TRANSFERRED"
    GRADUATED = "GRADUATED"
    DROPPED = "DROPPED"
    ALUMNI = "ALUMNI"
