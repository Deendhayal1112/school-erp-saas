from enum import Enum


class EmployeeType(str, Enum):
    TEACHING = "TEACHING"
    NON_TEACHING = "NON_TEACHING"
    ADMIN = "ADMIN"
    SUPPORT = "SUPPORT"


class EmploymentStatus(str, Enum):
    PROBATION = "PROBATION"
    CONFIRMED = "CONFIRMED"
    CONTRACT = "CONTRACT"
    RESIGNED = "RESIGNED"
    TERMINATED = "TERMINATED"


class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"


class BloodGroup(str, Enum):
    A_PLUS = "A_PLUS"
    A_MINUS = "A_MINUS"
    B_PLUS = "B_PLUS"
    B_MINUS = "B_MINUS"
    AB_PLUS = "AB_PLUS"
    AB_MINUS = "AB_MINUS"
    O_PLUS = "O_PLUS"
    O_MINUS = "O_MINUS"


class SalaryType(str, Enum):
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    HOURLY = "HOURLY"
