"""
Permission Engine.

Evaluates user permissions by walking the User → Role → RolePermission → Permission chain.
All permission codes are extracted from the eagerly-loaded ORM graph at request time,
then looked up via the cache layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


def _extract_permission_codes(user: User) -> frozenset[str]:
    """
    Traverses the ORM relationship graph and extracts all lowercase permission codes
    assigned to a user via their role.

    User → Role → RolePermission[] → Permission.code
    """
    if not user.role:
        return frozenset()
    codes: set[str] = set()
    for rp in user.role.role_permissions:
        if rp.permission and rp.permission.is_active and not rp.permission.is_deleted:
            codes.add(rp.permission.code.lower())
    return frozenset(codes)


def has_permission(user: User, permission_code: str) -> bool:
    """
    Returns True if the user holds the specified permission code.

    Super Admin role implicitly holds all permissions.
    """
    from app.auth.roles import is_super_admin

    if is_super_admin(user):
        return True

    codes = _extract_permission_codes(user)
    return permission_code.lower() in codes


def has_any_permission(user: User, *permission_codes: str) -> bool:
    """
    Returns True if the user holds at least one of the specified permission codes.
    """
    from app.auth.roles import is_super_admin

    if is_super_admin(user):
        return True

    codes = _extract_permission_codes(user)
    return any(p.lower() in codes for p in permission_codes)


def has_all_permissions(user: User, *permission_codes: str) -> bool:
    """
    Returns True if the user holds ALL of the specified permission codes.
    """
    from app.auth.roles import is_super_admin

    if is_super_admin(user):
        return True

    codes = _extract_permission_codes(user)
    return all(p.lower() in codes for p in permission_codes)


def permission_exists(user: User, permission_code: str) -> bool:
    """
    Returns True if the permission code is at all represented in the user's role.
    Unlike has_permission(), this does NOT apply Super Admin bypass.
    Useful for diagnostic and audit checks.
    """
    codes = _extract_permission_codes(user)
    return permission_code.lower() in codes


def get_user_permissions(user: User) -> list[str]:
    """Returns the sorted list of permission codes held by the user's role."""
    return sorted(_extract_permission_codes(user))
