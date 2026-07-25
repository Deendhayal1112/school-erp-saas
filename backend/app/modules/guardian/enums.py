from enum import Enum


class Relationship(str, Enum):
    """Enumeration representing the guardian's relationship type to a student."""

    FATHER = "FATHER"
    MOTHER = "MOTHER"
    GRANDFATHER = "GRANDFATHER"
    GRANDMOTHER = "GRANDMOTHER"
    BROTHER = "BROTHER"
    SISTER = "SISTER"
    UNCLE = "UNCLE"
    AUNT = "AUNT"
    LEGAL_GUARDIAN = "LEGAL_GUARDIAN"
    OTHER = "OTHER"
