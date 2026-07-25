"""
app/auth — Enterprise RBAC Authorization Package.

Public surface area for the authorization layer:
  - Permission Engine    (permissions.py)
  - Role Engine          (roles.py)
  - Authorization Logic  (authorization.py)
  - Cache Layer          (cache.py)
  - FastAPI Dependencies (rbac.py)
  - Exceptions           (exceptions.py)
"""

from app.auth.exceptions import (
    AuthorizationException,
    ForbiddenException,
    MissingPermissionException,
    MissingRoleException,
    PermissionDeniedException,
    RoleDeniedException,
    UnauthorizedException,
)
from app.auth.permissions import (
    get_user_permissions,
    has_all_permissions,
    has_any_permission,
    has_permission,
    permission_exists,
)
from app.auth.rbac import (
    RequireAllPermissions,
    RequireAnyPermission,
    RequireAnyRole,
    RequireMinimumRole,
    RequirePermission,
    RequireRole,
)
from app.auth.roles import (
    ROLE_ACCOUNTANT,
    ROLE_HIERARCHY,
    ROLE_PARENT,
    ROLE_PRINCIPAL,
    ROLE_SCHOOL_ADMIN,
    ROLE_STUDENT,
    ROLE_SUPER_ADMIN,
    ROLE_TEACHER,
    get_role_level,
    get_user_role,
    has_any_role,
    has_minimum_role,
    has_role,
    is_accountant,
    is_parent,
    is_principal,
    is_school_admin,
    is_student,
    is_super_admin,
    is_teacher,
    outranks,
)

__all__ = [
    # Exceptions
    "AuthorizationException",
    "UnauthorizedException",
    "ForbiddenException",
    "PermissionDeniedException",
    "RoleDeniedException",
    "MissingPermissionException",
    "MissingRoleException",
    # Permission engine
    "has_permission",
    "has_any_permission",
    "has_all_permissions",
    "permission_exists",
    "get_user_permissions",
    # Role engine
    "has_role",
    "has_any_role",
    "has_minimum_role",
    "get_role_level",
    "get_user_role",
    "outranks",
    "is_super_admin",
    "is_school_admin",
    "is_principal",
    "is_teacher",
    "is_accountant",
    "is_student",
    "is_parent",
    # Role constants
    "ROLE_SUPER_ADMIN",
    "ROLE_SCHOOL_ADMIN",
    "ROLE_PRINCIPAL",
    "ROLE_TEACHER",
    "ROLE_ACCOUNTANT",
    "ROLE_STUDENT",
    "ROLE_PARENT",
    "ROLE_HIERARCHY",
    # FastAPI dependency factories
    "RequirePermission",
    "RequireAnyPermission",
    "RequireAllPermissions",
    "RequireRole",
    "RequireAnyRole",
    "RequireMinimumRole",
]
