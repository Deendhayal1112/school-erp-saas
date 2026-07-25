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
