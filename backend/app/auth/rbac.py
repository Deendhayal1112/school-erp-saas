"""
RBAC FastAPI Dependency Factories.

Provides reusable callables compatible with FastAPI's Depends() system.
Each factory returns a dependency function that raises HTTP 403 Forbidden
when authorization fails, mapping cleanly to the exception handlers in main.py.

Usage examples:
    @router.post("/students", dependencies=[Depends(RequirePermission("student.create"))])
    @router.get("/fees", dependencies=[Depends(RequireRole("ACCOUNTANT"))])
    @router.delete("/users/{id}", dependencies=[Depends(RequireAnyRole("SUPER_ADMIN", "SCHOOL_ADMIN"))])
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.auth import authorization as authz
from app.dependencies.current_user import get_current_active_user
from app.models.user import User


# ===========================================================================
# Permission-based Dependency Factories
# ===========================================================================
def RequirePermission(permission_code: str) -> Callable:
    """
    FastAPI dependency factory.
    Authorizes requests where the user holds the specified permission code.

    - Super Admin role bypasses all permission checks.
    - Raises HTTP 403 via PermissionDeniedException if check fails.

    Example:
        @router.post("/students", dependencies=[Depends(RequirePermission("student.create"))])
    """

    async def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        await authz.require_permission(current_user, permission_code)
        return current_user

    dependency.__name__ = f"require_permission_{permission_code}"
    dependency.__doc__ = (
        f"**Authentication Required** | **Permission Required**: `{permission_code}`"
    )
    return dependency


def RequireAnyPermission(*permission_codes: str) -> Callable:
    """
    FastAPI dependency factory.
    Authorizes requests where the user holds at least one of the specified permissions.

    Example:
        @router.get("/reports", dependencies=[Depends(RequireAnyPermission("report.view", "report.export"))])
    """

    async def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        await authz.require_any_permission(current_user, *permission_codes)
        return current_user

    dependency.__name__ = f"require_any_permission_{'_or_'.join(permission_codes)}"
    dependency.__doc__ = (
        f"**Authentication Required** | **Any Permission Required**: "
        f"`{'` or `'.join(permission_codes)}`"
    )
    return dependency


def RequireAllPermissions(*permission_codes: str) -> Callable:
    """
    FastAPI dependency factory.
    Authorizes requests where the user holds ALL of the specified permissions.

    Example:
        @router.post("/exams/publish", dependencies=[Depends(RequireAllPermissions("exam.create", "exam.publish"))])
    """

    async def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        await authz.require_all_permissions(current_user, *permission_codes)
        return current_user

    dependency.__name__ = f"require_all_permissions_{'_and_'.join(permission_codes)}"
    dependency.__doc__ = (
        f"**Authentication Required** | **All Permissions Required**: "
        f"`{'`, `'.join(permission_codes)}`"
    )
    return dependency


# ===========================================================================
# Role-based Dependency Factories
# ===========================================================================
def RequireRole(role_code: str) -> Callable:
    """
    FastAPI dependency factory.
    Authorizes requests where the user holds exactly the specified role.

    Example:
        @router.delete("/school/{id}", dependencies=[Depends(RequireRole("SUPER_ADMIN"))])
    """

    async def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        await authz.require_role(current_user, role_code)
        return current_user

    dependency.__name__ = f"require_role_{role_code}"
    dependency.__doc__ = (
        f"**Authentication Required** | **Role Required**: `{role_code}`"
    )
    return dependency


def RequireAnyRole(*role_codes: str) -> Callable:
    """
    FastAPI dependency factory.
    Authorizes requests where the user holds at least one of the specified roles.

    Example:
        @router.get("/dashboard", dependencies=[Depends(RequireAnyRole("SUPER_ADMIN", "SCHOOL_ADMIN", "PRINCIPAL"))])
    """

    async def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        await authz.require_any_role(current_user, *role_codes)
        return current_user

    dependency.__name__ = f"require_any_role_{'_or_'.join(role_codes)}"
    dependency.__doc__ = (
        f"**Authentication Required** | **Any Role Required**: "
        f"`{'` or `'.join(role_codes)}`"
    )
    return dependency


def RequireMinimumRole(minimum_role_code: str) -> Callable:
    """
    FastAPI dependency factory.
    Authorizes requests where the user's role is at or above the minimum in the hierarchy.

    Example:
        @router.get("/staff", dependencies=[Depends(RequireMinimumRole("PRINCIPAL"))])
        # Allows SUPER_ADMIN, SCHOOL_ADMIN, PRINCIPAL but not TEACHER, STUDENT, etc.
    """

    async def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        await authz.require_minimum_role(current_user, minimum_role_code)
        return current_user

    dependency.__name__ = f"require_minimum_role_{minimum_role_code}"
    dependency.__doc__ = f"**Authentication Required** | **Minimum Role Required**: `{minimum_role_code}` or higher"
    return dependency
