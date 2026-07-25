"""
Email Verification & Recovery Exceptions.
"""

class EmailException(Exception):
    """Base exception for all email-related failures."""
    pass

class InvalidVerificationTokenException(EmailException):
    """Raised when the email verification token is invalid, used, or not found."""
    pass

class ExpiredVerificationTokenException(EmailException):
    """Raised when the email verification token has expired."""
    pass

class EmailRateLimitException(EmailException):
    """Raised when the user requests verification emails too frequently (rate limiting)."""
    pass

class AccountAlreadyVerifiedException(EmailException):
    """Raised when attempting to verify an email for an account that is already active/verified."""
    pass
