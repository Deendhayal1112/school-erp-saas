from enum import Enum


class AdmissionStatus(str, Enum):
    """Enumeration representing the stages of the student admission workflow."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WAITLISTED = "WAITLISTED"
    ENROLLED = "ENROLLED"
