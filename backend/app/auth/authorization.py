"""
Authorization Engine.

Thin orchestration layer that wires the Permission Engine, Role Engine,
and Cache Layer together into a single cohesive authorization decision interface.

Design principles:
  - All public functions are pure Python (no FastAPI dependencies).
  - FastAPI dependencies live in rbac.py and import from here.
  - Caching is transparent to callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.auth import cache as rbac_cache
from app.auth import permissions as perm_engine
from app.auth import roles as role_engine
from app.auth.exceptions import (
    MissingRoleException,
    PermissionDeniedException,
    RoleDeniedException,
)

if TYPE_CHECKING:
    from app.models.user import User


# ===========================================================================
# Cached Permission Resolution
# ===========================================================================
async def resolve_permissions(user: User) -> frozenset[str]:
    """
    Returns the full set of permission codes for the user.
    Results are cached per-user; first call loads from ORM graph.
    """
    cached = await rbac_cache.get_cached_permissions(user.id)
    if cached is not None:
        return cached

    permissions = perm_engine._extract_permission_codes(user)
    await rbac_cache.set_cached_permissions(user.id, permissions)
    return permissions


async def resolve_role(user: User) -> str | None:
    """
    Returns the role code for the user.
    Results are cached per-user; first call loads from ORM graph.
    """
    cached = await rbac_cache.get_cached_role(user.id)
    if cached is not None:
        return cached

    role_code = role_engine.get_user_role(user)
    if role_code:
        await rbac_cache.set_cached_role(user.id, role_code)
    return role_code


# ===========================================================================
# Authorization Checks (raise on failure)
# ===========================================================================
async def require_permission(user: User, permission_code: str) -> None:
    """
    Asserts the user holds the required permission code.
    Raises PermissionDeniedException if the check fails.
    """
    if not perm_engine.has_permission(user, permission_code):
        raise PermissionDeniedException(permission_code)


async def require_any_permission(user: User, *permission_codes: str) -> None:
    """
    Asserts the user holds at least one of the specified permissions.
    Raises PermissionDeniedException with the first missing code if none match.
    """
    if not perm_engine.has_any_permission(user, *permission_codes):
        raise PermissionDeniedException(", ".join(permission_codes))


async def require_all_permissions(user: User, *permission_codes: str) -> None:
    """
    Asserts the user holds ALL of the specified permissions.
    Raises PermissionDeniedException for the first missing permission code.
    """
    user_perms = perm_engine._extract_permission_codes(user)
    if not role_engine.is_super_admin(user):
        for code in permission_codes:
            if code.lower() not in user_perms:
                raise PermissionDeniedException(code)


async def require_role(user: User, role_code: str) -> None:
    """
    Asserts the user holds the exact specified role.
    Raises RoleDeniedException if the check fails.
    Raises MissingRoleException if the user has no role assigned at all.
    """
    if not user.role:
        raise MissingRoleException()
    if not role_engine.has_role(user, role_code):
        raise RoleDeniedException(role_code)


async def require_any_role(user: User, *role_codes: str) -> None:
    """
    Asserts the user holds at least one of the specified roles.
    Raises RoleDeniedException if no match.
    """
    if not user.role:
        raise MissingRoleException()
    if not role_engine.has_any_role(user, *role_codes):
        raise RoleDeniedException(", ".join(role_codes))


async def require_minimum_role(user: User, minimum_role_code: str) -> None:
    """
    Asserts the user's role is at or above the minimum level in the role hierarchy.
    Raises RoleDeniedException if the user's role is below the required level.
    """
    if not role_engine.has_minimum_role(user, minimum_role_code):
        raise RoleDeniedException(f"at least {minimum_role_code}")
