"""
RBAC Unit & Integration Tests — Phase 3 Step 8.

Tests cover:
  - Permission engine (has_permission, has_any/all)
  - Role engine (has_role, hierarchy, named helpers)
  - Super Admin bypass on permissions
  - Denial scenarios: missing permission, missing role
  - Permission caching (set/get/invalidate)
  - Role hierarchy ordering and outranks()
  - FastAPI dependency factories via httpx ASGI client

Fixtures build lightweight User/Role/RolePermission/Permission ORM objects
in-memory (no DB required for engine unit tests).
"""

import uuid
from unittest.mock import MagicMock

import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.auth import (
    RequirePermission,
    RequireRole,
    has_all_permissions,
    has_any_permission,
    has_permission,
    has_role,
    is_accountant,
    is_parent,
    is_principal,
    is_school_admin,
    is_student,
    is_super_admin,
    is_teacher,
    permission_exists,
)
from app.auth.cache import (
    clear_local_cache,
    get_cached_permissions,
    get_cached_role,
    invalidate_user_cache,
    set_cached_permissions,
    set_cached_role,
)
from app.auth.exceptions import (
    MissingRoleException,
    PermissionDeniedException,
    RoleDeniedException,
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
    has_minimum_role,
    outranks,
)
from app.auth import authorization as authz
from app.main import app


# ===========================================================================
# Test Helpers — Build mock ORM objects without database
# ===========================================================================
def make_permission(code: str, module: str = "test") -> MagicMock:
    p = MagicMock()
    p.code = code
    p.module = module
    p.is_active = True
    p.is_deleted = False
    return p


def make_role_permission(perm_code: str) -> MagicMock:
    rp = MagicMock()
    rp.permission = make_permission(perm_code)
    return rp


def make_role(code: str, *permission_codes: str) -> MagicMock:
    role = MagicMock()
    role.code = code
    role.role_permissions = [make_role_permission(c) for c in permission_codes]
    return role


def make_user(role_code: str, *permission_codes: str) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = make_role(role_code, *permission_codes)
    return user


def make_user_no_role() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = None
    return user


# ===========================================================================
# Permission Engine Tests
# ===========================================================================
class TestPermissionEngine:

    def test_super_admin_has_all_permissions(self):
        """Super Admin bypasses all permission checks — always returns True."""
        user = make_user(ROLE_SUPER_ADMIN)
        assert has_permission(user, "student.create") is True
        assert has_permission(user, "fee.collect") is True
        assert has_permission(user, "nonexistent.permission") is True

    def test_has_permission_granted(self):
        """User with explicit permission returns True."""
        user = make_user(ROLE_TEACHER, "student.view", "attendance.mark")
        assert has_permission(user, "student.view") is True
        assert has_permission(user, "attendance.mark") is True

    def test_has_permission_denied(self):
        """User without explicit permission returns False."""
        user = make_user(ROLE_TEACHER, "student.view")
        assert has_permission(user, "fee.collect") is False

    def test_has_permission_case_insensitive(self):
        """Permission codes are normalized to lowercase."""
        user = make_user(ROLE_TEACHER, "student.view")
        assert has_permission(user, "STUDENT.VIEW") is True
        assert has_permission(user, "Student.View") is True

    def test_has_permission_no_role(self):
        """User with no role assigned never holds any permissions."""
        user = make_user_no_role()
        assert has_permission(user, "student.view") is False

    def test_has_any_permission_one_match(self):
        """Returns True when at least one permission matches."""
        user = make_user(ROLE_ACCOUNTANT, "fee.collect", "fee.view")
        assert has_any_permission(user, "fee.collect", "student.create") is True

    def test_has_any_permission_no_match(self):
        """Returns False when none of the permissions match."""
        user = make_user(ROLE_PARENT, "fee.view")
        assert has_any_permission(user, "student.create", "fee.collect") is False

    def test_has_all_permissions_all_match(self):
        """Returns True only when every permission matches."""
        user = make_user(ROLE_PRINCIPAL, "student.view", "attendance.view", "exam.publish")
        assert has_all_permissions(user, "student.view", "attendance.view") is True

    def test_has_all_permissions_partial_match(self):
        """Returns False if even one permission is missing."""
        user = make_user(ROLE_TEACHER, "attendance.mark")
        assert has_all_permissions(user, "attendance.mark", "fee.collect") is False

    def test_permission_exists_direct_check(self):
        """permission_exists does NOT apply super admin bypass."""
        user = make_user(ROLE_SUPER_ADMIN)  # super admin but no explicit permissions
        # Super Admin role in seed has no permissions loaded in this mock
        assert permission_exists(user, "fee.collect") is False

    def test_super_admin_has_any_permission_bypass(self):
        """Super Admin has_any_permission always True."""
        user = make_user(ROLE_SUPER_ADMIN)
        assert has_any_permission(user, "unknown.perm") is True

    def test_super_admin_has_all_permissions_bypass(self):
        """Super Admin has_all_permissions always True."""
        user = make_user(ROLE_SUPER_ADMIN)
        assert has_all_permissions(user, "a.b", "c.d", "e.f") is True


# ===========================================================================
# Role Engine Tests
# ===========================================================================
class TestRoleEngine:

    def test_has_role_match(self):
        user = make_user(ROLE_SUPER_ADMIN)
        assert has_role(user, ROLE_SUPER_ADMIN) is True

    def test_has_role_mismatch(self):
        user = make_user(ROLE_TEACHER)
        assert has_role(user, ROLE_SUPER_ADMIN) is False

    def test_has_role_case_insensitive(self):
        user = make_user("teacher")
        assert has_role(user, "TEACHER") is True

    def test_is_super_admin_true(self):
        assert is_super_admin(make_user(ROLE_SUPER_ADMIN)) is True

    def test_is_super_admin_false(self):
        assert is_super_admin(make_user(ROLE_SCHOOL_ADMIN)) is False

    def test_is_school_admin(self):
        assert is_school_admin(make_user(ROLE_SCHOOL_ADMIN)) is True
        assert is_school_admin(make_user(ROLE_PRINCIPAL)) is False

    def test_is_principal(self):
        assert is_principal(make_user(ROLE_PRINCIPAL)) is True
        assert is_principal(make_user(ROLE_TEACHER)) is False

    def test_is_teacher(self):
        assert is_teacher(make_user(ROLE_TEACHER)) is True

    def test_is_accountant(self):
        assert is_accountant(make_user(ROLE_ACCOUNTANT)) is True

    def test_is_student(self):
        assert is_student(make_user(ROLE_STUDENT)) is True

    def test_is_parent(self):
        assert is_parent(make_user(ROLE_PARENT)) is True

    def test_role_hierarchy_order(self):
        """Role hierarchy list is in the expected order."""
        assert ROLE_HIERARCHY[0] == ROLE_SUPER_ADMIN
        assert ROLE_HIERARCHY[-1] == ROLE_PARENT

    def test_get_role_level_super_admin_lowest_index(self):
        """Super Admin has the lowest (most privileged) index."""
        super_admin_user = make_user(ROLE_SUPER_ADMIN)
        teacher_user = make_user(ROLE_TEACHER)
        assert get_role_level(super_admin_user) < get_role_level(teacher_user)

    def test_has_minimum_role_super_admin_passes_all(self):
        """Super Admin passes every minimum role check."""
        user = make_user(ROLE_SUPER_ADMIN)
        for role in ROLE_HIERARCHY:
            assert has_minimum_role(user, role) is True

    def test_has_minimum_role_teacher_fails_principal(self):
        """Teacher does not meet the minimum Principal threshold."""
        user = make_user(ROLE_TEACHER)
        assert has_minimum_role(user, ROLE_PRINCIPAL) is False

    def test_has_minimum_role_teacher_passes_teacher(self):
        """Teacher meets exactly the Teacher minimum threshold."""
        user = make_user(ROLE_TEACHER)
        assert has_minimum_role(user, ROLE_TEACHER) is True

    def test_outranks_super_admin_over_teacher(self):
        """Super Admin outranks Teacher."""
        sa = make_user(ROLE_SUPER_ADMIN)
        teacher = make_user(ROLE_TEACHER)
        assert outranks(sa, teacher) is True
        assert outranks(teacher, sa) is False

    def test_outranks_same_role_false(self):
        """Same role does not outrank itself."""
        u1 = make_user(ROLE_PRINCIPAL)
        u2 = make_user(ROLE_PRINCIPAL)
        assert outranks(u1, u2) is False

    def test_no_role_assigned(self):
        """User with no role returns None from get_user_role."""
        from app.auth.roles import get_user_role
        user = make_user_no_role()
        assert get_user_role(user) is None


# ===========================================================================
# Authorization Engine (require_* async assertions)
# ===========================================================================
class TestAuthorizationEngine:

    @pytest.mark.asyncio
    async def test_require_permission_success(self):
        user = make_user(ROLE_TEACHER, "attendance.mark")
        await authz.require_permission(user, "attendance.mark")  # must not raise

    @pytest.mark.asyncio
    async def test_require_permission_denied(self):
        user = make_user(ROLE_TEACHER, "attendance.mark")
        with pytest.raises(PermissionDeniedException):
            await authz.require_permission(user, "fee.collect")

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        user = make_user(ROLE_PRINCIPAL)
        await authz.require_role(user, ROLE_PRINCIPAL)  # must not raise

    @pytest.mark.asyncio
    async def test_require_role_denied(self):
        user = make_user(ROLE_TEACHER)
        with pytest.raises(RoleDeniedException):
            await authz.require_role(user, ROLE_PRINCIPAL)

    @pytest.mark.asyncio
    async def test_require_role_no_role_assigned(self):
        user = make_user_no_role()
        with pytest.raises(MissingRoleException):
            await authz.require_role(user, ROLE_TEACHER)

    @pytest.mark.asyncio
    async def test_require_any_permission_success(self):
        user = make_user(ROLE_ACCOUNTANT, "fee.collect")
        await authz.require_any_permission(user, "fee.view", "fee.collect")

    @pytest.mark.asyncio
    async def test_require_any_permission_denied(self):
        user = make_user(ROLE_PARENT, "fee.view")
        with pytest.raises(PermissionDeniedException):
            await authz.require_any_permission(user, "student.create", "fee.collect")

    @pytest.mark.asyncio
    async def test_require_all_permissions_success(self):
        user = make_user(ROLE_PRINCIPAL, "student.view", "attendance.view")
        await authz.require_all_permissions(user, "student.view", "attendance.view")

    @pytest.mark.asyncio
    async def test_require_all_permissions_partial_denied(self):
        user = make_user(ROLE_TEACHER, "attendance.mark")
        with pytest.raises(PermissionDeniedException):
            await authz.require_all_permissions(user, "attendance.mark", "fee.collect")

    @pytest.mark.asyncio
    async def test_require_minimum_role_passes(self):
        user = make_user(ROLE_SCHOOL_ADMIN)
        await authz.require_minimum_role(user, ROLE_PRINCIPAL)

    @pytest.mark.asyncio
    async def test_require_minimum_role_denied(self):
        user = make_user(ROLE_STUDENT)
        with pytest.raises(RoleDeniedException):
            await authz.require_minimum_role(user, ROLE_TEACHER)


# ===========================================================================
# Permission Cache Tests
# ===========================================================================
class TestPermissionCache:

    @pytest.mark.asyncio
    async def test_cache_set_and_get_permissions(self):
        """Cache stores and retrieves permission sets correctly."""
        clear_local_cache()
        user_id = uuid.uuid4()
        perms = frozenset(["student.view", "attendance.mark"])
        await set_cached_permissions(user_id, perms)
        result = await get_cached_permissions(user_id)
        assert result == perms

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        """Cache miss returns None for unknown user ID."""
        clear_local_cache()
        result = await get_cached_permissions(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get_role(self):
        """Cache stores and retrieves role codes correctly."""
        clear_local_cache()
        user_id = uuid.uuid4()
        await set_cached_role(user_id, ROLE_TEACHER)
        result = await get_cached_role(user_id)
        assert result == ROLE_TEACHER

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """invalidate_user_cache removes both permissions and role for a user."""
        clear_local_cache()
        user_id = uuid.uuid4()
        await set_cached_permissions(user_id, frozenset(["fee.collect"]))
        await set_cached_role(user_id, ROLE_ACCOUNTANT)

        await invalidate_user_cache(user_id)

        assert await get_cached_permissions(user_id) is None
        assert await get_cached_role(user_id) is None

    @pytest.mark.asyncio
    async def test_resolve_permissions_uses_cache(self):
        """resolve_permissions returns cached data on second call without touching ORM."""
        clear_local_cache()
        user = make_user(ROLE_TEACHER, "attendance.mark")
        # First call: loads from ORM, stores in cache
        perms_first = await authz.resolve_permissions(user)
        # Second call with a fresh mock (no role_permissions) should return cached result
        user_cached = make_user_no_role()
        user_cached.id = user.id  # same user ID → cache hit
        perms_second = await authz.resolve_permissions(user_cached)
        assert perms_first == perms_second


# ===========================================================================
# API Integration: RequirePermission / RequireRole dependencies
# ===========================================================================
BASE = "/api/v1/auth"
SEEDED_EMAIL = "superadmin@schoolerpsaas.com"
SEEDED_PASSWORD = "Admin@1234"


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def superadmin_token(client: AsyncClient) -> str:
    resp = await client.post(
        f"{BASE}/login",
        json={"email": SEEDED_EMAIL, "password": SEEDED_PASSWORD},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_super_admin_can_access_protected_me_endpoint(
    client: AsyncClient, superadmin_token: str
):
    """Super Admin can access /me — verifying the auth + RBAC layer works end-to-end."""
    resp = await client.get(
        f"{BASE}/me",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == ROLE_SUPER_ADMIN


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(client: AsyncClient):
    """Requests without tokens to protected endpoints return 401."""
    resp = await client.get(f"{BASE}/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_super_admin_token_contains_correct_role(
    client: AsyncClient, superadmin_token: str
):
    """Super Admin /me response exposes the SUPER_ADMIN role code."""
    resp = await client.get(
        f"{BASE}/me",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == ROLE_SUPER_ADMIN
