"""
Permission Cache Layer.

Provides a transparent two-tier caching strategy for RBAC permission lookups:

  1. Primary (Redis): If Redis is reachable, permissions are cached in Redis
     with a configurable TTL. Useful in multi-process / multi-pod deployments
     where invalidation must propagate across nodes.

  2. Fallback (in-process dict): If Redis is unavailable, an in-process
     TTL-aware dict is used. Sufficient for single-process dev/test environments.

Cache Keys:
  rbac:perms:<user_id>  → frozenset of permission code strings
  rbac:role:<user_id>   → role code string

Invalidation:
  Call invalidate_user_cache(user_id) after role or permission changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default TTL for cached permission sets (seconds)
_CACHE_TTL_SECONDS: int = 300  # 5 minutes

# ===========================================================================
# In-process fallback cache (used when Redis is unavailable)
# ===========================================================================
_LOCAL_CACHE: dict[str, tuple[object, float]] = {}
_LOCAL_CACHE_LOCK = asyncio.Lock()


def _local_get(key: str) -> object | None:
    entry = _LOCAL_CACHE.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        _LOCAL_CACHE.pop(key, None)
        return None
    return value


def _local_set(key: str, value: object, ttl: int = _CACHE_TTL_SECONDS) -> None:
    _LOCAL_CACHE[key] = (value, time.monotonic() + ttl)


def _local_delete(key: str) -> None:
    _LOCAL_CACHE.pop(key, None)


def _local_delete_prefix(prefix: str) -> None:
    keys = [k for k in _LOCAL_CACHE if k.startswith(prefix)]
    for k in keys:
        _LOCAL_CACHE.pop(k, None)


# ===========================================================================
# Redis operations (best-effort: silently falls back on error)
# ===========================================================================
_redis_client = None
_redis_initialized: bool = False


async def _get_redis():
    """Returns a connected Redis client or None if Redis is unavailable."""
    global _redis_client, _redis_initialized
    if _redis_initialized:
        return _redis_client
    _redis_initialized = True
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
        )
        await client.ping()
        _redis_client = client
        logger.info("RBAC cache: Redis connected at %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning(
            "RBAC cache: Redis unavailable (%s), falling back to in-process cache.", exc
        )
        _redis_client = None
    return _redis_client


# ===========================================================================
# Public Cache API
# ===========================================================================
async def get_cached_permissions(user_id: uuid.UUID) -> frozenset[str] | None:
    """Retrieves the cached permission code set for a user, or None on cache miss."""
    key = f"rbac:perms:{user_id}"
    redis = await _get_redis()
    if redis is not None:
        try:
            raw = await redis.get(key)
            if raw:
                return frozenset(json.loads(raw))
        except Exception as exc:
            logger.debug("RBAC Redis get error: %s", exc)

    # Fallback to local
    value = _local_get(key)
    if value is not None:
        return frozenset(value)  # type: ignore[arg-type]
    return None


async def set_cached_permissions(
    user_id: uuid.UUID, permissions: frozenset[str], ttl: int = _CACHE_TTL_SECONDS
) -> None:
    """Persists the permission code set to cache."""
    key = f"rbac:perms:{user_id}"
    serialized = json.dumps(sorted(permissions))

    redis = await _get_redis()
    if redis is not None:
        try:
            await redis.set(key, serialized, ex=ttl)
            return
        except Exception as exc:
            logger.debug("RBAC Redis set error: %s", exc)

    # Fallback to local
    _local_set(key, list(permissions), ttl)


async def get_cached_role(user_id: uuid.UUID) -> str | None:
    """Retrieves the cached role code for a user, or None on cache miss."""
    key = f"rbac:role:{user_id}"
    redis = await _get_redis()
    if redis is not None:
        try:
            return await redis.get(key)
        except Exception as exc:
            logger.debug("RBAC Redis get error: %s", exc)

    value = _local_get(key)
    return str(value) if value is not None else None


async def set_cached_role(
    user_id: uuid.UUID, role_code: str, ttl: int = _CACHE_TTL_SECONDS
) -> None:
    """Persists the role code to cache."""
    key = f"rbac:role:{user_id}"
    redis = await _get_redis()
    if redis is not None:
        try:
            await redis.set(key, role_code, ex=ttl)
            return
        except Exception as exc:
            logger.debug("RBAC Redis set error: %s", exc)

    _local_set(key, role_code, ttl)


async def invalidate_user_cache(user_id: uuid.UUID) -> None:
    """
    Removes all RBAC cache entries for a given user.
    Call after role changes, permission updates, or account deactivation.
    """
    perms_key = f"rbac:perms:{user_id}"
    role_key = f"rbac:role:{user_id}"

    redis = await _get_redis()
    if redis is not None:
        try:
            await redis.delete(perms_key, role_key)
        except Exception as exc:
            logger.debug("RBAC Redis delete error: %s", exc)

    # Also purge from local fallback
    _local_delete(perms_key)
    _local_delete(role_key)
    logger.debug("RBAC cache invalidated for user %s", user_id)


async def invalidate_role_cache(role_code: str) -> None:
    """
    Invalidates the in-process cache for all users bearing a specific role.
    For Redis, performs a SCAN-based key deletion (best-effort, non-blocking).
    Useful after bulk permission changes to a role.
    """
    # Clear local cache entirely on role-wide invalidation
    _local_delete_prefix("rbac:")

    redis = await _get_redis()
    if redis is not None:
        try:
            async for key in redis.scan_iter("rbac:*"):
                await redis.delete(key)
        except Exception as exc:
            logger.debug("RBAC Redis scan/delete error: %s", exc)

    logger.info("RBAC cache cleared for role '%s'", role_code)


def clear_local_cache() -> None:
    """Clears the entire in-process local cache. Used in tests."""
    _LOCAL_CACHE.clear()
