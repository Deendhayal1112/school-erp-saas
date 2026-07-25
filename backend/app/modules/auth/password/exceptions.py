"""
Password Management Exceptions.
"""

from app.exceptions import AuthenticationFailedException

class PasswordException(Exception):
    """Base exception for all password-related business logic failures."""
    pass

class PasswordValidationError(PasswordException):
    """Raised when a password fails policy rules (length, complexity, dictionary, etc.)."""
    pass

class PasswordReuseException(PasswordValidationError):
    """Raised when a user attempts to reuse a password in their history."""
    pass

class InvalidCurrentPasswordException(PasswordException):
    """Raised when changing password but the current password check fails."""
    pass

class AccountLockedException(AuthenticationFailedException):
    """Raised when a login attempt is made on a temporarily locked user account."""
    def __init__(self, message: str, unlock_time=None):
        self.unlock_time = unlock_time
        super().__init__(message)

class InvalidResetTokenException(PasswordException):
    """Raised when a password reset token is invalid, used, or not found."""
    pass

class ExpiredResetTokenException(PasswordException):
    """Raised when a password reset token has expired."""
    pass
