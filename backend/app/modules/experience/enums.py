from enum import StrEnum


class EmploymentType(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERN = "INTERN"
    FREELANCE = "FREELANCE"


class OrganizationType(StrEnum):
    PRIVATE_SCHOOL = "PRIVATE_SCHOOL"
    GOVT_SCHOOL = "GOVT_SCHOOL"
    INTERNATIONAL_SCHOOL = "INTERNATIONAL_SCHOOL"
    PRIVATE_COMPANY = "PRIVATE_COMPANY"
    OTHER = "OTHER"


class ExperienceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
