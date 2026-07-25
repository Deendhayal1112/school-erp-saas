"""
Role Engine.

Evaluates user role membership by inspecting the User → Role relationship.
Provides well-typed role helpers and supports future role hierarchy expansion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

# ===========================================================================
# Canonical role code constants.
# These match the `code` column values inserted by the seed script.
# ===========================================================================
ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_SCHOOL_ADMIN = "SCHOOL_ADMIN"
ROLE_PRINCIPAL = "PRINCIPAL"
ROLE_TEACHER = "TEACHER"
ROLE_ACCOUNTANT = "ACCOUNTANT"
ROLE_STUDENT = "STUDENT"
ROLE_PARENT = "PARENT"

# Ordered hierarchy: index 0 = highest authority.
ROLE_HIERARCHY: list[str] = [
    ROLE_SUPER_ADMIN,
    ROLE_SCHOOL_ADMIN,
    ROLE_PRINCIPAL,
    ROLE_TEACHER,
    ROLE_ACCOUNTANT,
    ROLE_STUDENT,
    ROLE_PARENT,
]


def _get_role_code(user: User) -> str | None:
    """Safely extracts the uppercase role code from the user ORM graph."""
    if not user.role:
        return None
    return user.role.code.upper()


# ===========================================================================
# Single-role Checks
# ===========================================================================
def has_role(user: User, role_code: str) -> bool:
    """Returns True if the user's role code matches the given code (case-insensitive)."""
    code = _get_role_code(user)
    return code is not None and code == role_code.upper()


def has_any_role(user: User, *role_codes: str) -> bool:
    """Returns True if the user's role code matches any of the given codes."""
    code = _get_role_code(user)
    if code is None:
        return False
    return code in {r.upper() for r in role_codes}


# ===========================================================================
# Named Role Helpers
# ===========================================================================
def is_super_admin(user: User) -> bool:
    """Returns True if the user holds the SUPER_ADMIN role."""
    return has_role(user, ROLE_SUPER_ADMIN)


def is_school_admin(user: User) -> bool:
    """Returns True if the user holds the SCHOOL_ADMIN role."""
    return has_role(user, ROLE_SCHOOL_ADMIN)


def is_principal(user: User) -> bool:
    """Returns True if the user holds the PRINCIPAL role."""
    return has_role(user, ROLE_PRINCIPAL)


def is_teacher(user: User) -> bool:
    """Returns True if the user holds the TEACHER role."""
    return has_role(user, ROLE_TEACHER)


def is_accountant(user: User) -> bool:
    """Returns True if the user holds the ACCOUNTANT role."""
    return has_role(user, ROLE_ACCOUNTANT)


def is_student(user: User) -> bool:
    """Returns True if the user holds the STUDENT role."""
    return has_role(user, ROLE_STUDENT)


def is_parent(user: User) -> bool:
    """Returns True if the user holds the PARENT role."""
    return has_role(user, ROLE_PARENT)


# ===========================================================================
# Hierarchy Checks
# ===========================================================================
def has_minimum_role(user: User, minimum_role_code: str) -> bool:
    """
    Returns True if the user's role is at or above the minimum role
    in the defined ROLE_HIERARCHY (index 0 = highest).

    Example: has_minimum_role(user, "PRINCIPAL")
      → True for SUPER_ADMIN, SCHOOL_ADMIN, PRINCIPAL
      → False for TEACHER, STUDENT, PARENT
    """
    code = _get_role_code(user)
    if code is None:
        return False
    try:
        user_index = ROLE_HIERARCHY.index(code)
        min_index = ROLE_HIERARCHY.index(minimum_role_code.upper())
        return user_index <= min_index
    except ValueError:
        return False


def get_role_level(user: User) -> int:
    """
    Returns the user's role hierarchy level (0 = highest authority).
    Returns len(ROLE_HIERARCHY) if the role is not in the hierarchy.
    """
    code = _get_role_code(user)
    if code is None:
        return len(ROLE_HIERARCHY)
    try:
        return ROLE_HIERARCHY.index(code)
    except ValueError:
        return len(ROLE_HIERARCHY)


def outranks(user: User, other_user: User) -> bool:
    """
    Returns True if user has a higher authority role than other_user.
    Lower hierarchy index = higher authority.
    """
    return get_role_level(user) < get_role_level(other_user)


def get_user_role(user: User) -> str | None:
    """Returns the role code of the user, or None if no role is assigned."""
    return _get_role_code(user)
