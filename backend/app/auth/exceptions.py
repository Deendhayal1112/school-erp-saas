"""
Enterprise RBAC Authorization Exceptions.

All authorization-layer exceptions are business-domain exceptions
(not FastAPI HTTP exceptions). They are mapped to HTTP responses in main.py.
"""


class AuthorizationException(Exception):
    """Base exception for all authorization-related failures."""
    pass


class UnauthorizedException(AuthorizationException):
    """Raised when an unauthenticated user attempts to access a protected resource."""
    pass


class ForbiddenException(AuthorizationException):
    """Raised when a user is authenticated but lacks the required role or permission."""
    pass


class PermissionDeniedException(ForbiddenException):
    """Raised when the user does not hold a specific required permission code."""

    def __init__(self, permission: str):
        self.permission = permission
        super().__init__(f"Permission denied: '{permission}' is required.")


class RoleDeniedException(ForbiddenException):
    """Raised when the user does not hold a specific required role code."""

    def __init__(self, role: str):
        self.role = role
        super().__init__(f"Role denied: '{role}' role is required.")


class MissingPermissionException(ForbiddenException):
    """Raised when a permission check is attempted but no permissions are assigned."""

    def __init__(self, permission: str):
        self.permission = permission
        super().__init__(f"Missing permission: '{permission}' is not configured.")


class MissingRoleException(ForbiddenException):
    """Raised when a role check is attempted but the user has no role assigned."""

    def __init__(self):
        super().__init__("No role is assigned to this user account.")
