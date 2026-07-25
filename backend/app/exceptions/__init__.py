class RepositoryError(Exception):
    """Base exception for all repository data operations."""
    pass


class EntityNotFoundError(RepositoryError):
    """Raised when a requested database entity does not exist."""
    pass


class DuplicateEntityError(RepositoryError):
    """Raised when a unique constraint or index violation occurs (e.g. duplicate email)."""
    pass


class DatabaseError(RepositoryError):
    """Fallback exception representing underlying database driver or execution failures."""
    pass


# ==========================================
# Business-level Authentication Exceptions
# ==========================================
class AuthenticationFailedException(Exception):
    """Base exception for all authentication-related failures."""
    pass


class InvalidCredentialsException(AuthenticationFailedException):
    """Raised when authentication credentials (email/password) fail validation checks."""
    pass


class InactiveUserException(AuthenticationFailedException):
    """Raised when the user account active status flag is set to False."""
    pass


class DeletedUserException(AuthenticationFailedException):
    """Raised when the user account is marked soft-deleted."""
    pass


class InactiveSchoolException(AuthenticationFailedException):
    """Raised when the user's associated school tenant status is inactive."""
    pass


class TokenExpiredException(AuthenticationFailedException):
    """Raised when a cryptographic signature token has expired."""
    pass


class RefreshTokenException(AuthenticationFailedException):
    """Raised on invalid or malformed refresh token signature payloads."""
    pass

