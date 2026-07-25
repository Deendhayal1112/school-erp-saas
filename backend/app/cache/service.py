"""
Caching and Distributed Locking Service Layer.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fallback local dictionary cache
_LOCAL_STORE: dict[str, tuple[str, float]] = {}
_LOCAL_STORE_LOCK = asyncio.Lock()


class RedisLock:
    """Distributed lock context manager using Redis SET NX."""

    def __init__(self, client: Any, key: str, timeout: int = 10) -> None:
        self.client = client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.acquired = False

    async def __aenter__(self) -> "RedisLock":
        # Attempt to acquire lock (SET key val EX timeout NX)
        if self.client is not None:
            try:
                res = await self.client.set(self.key, "1", ex=self.timeout, nx=True)
                self.acquired = bool(res)
            except Exception as exc:
                logger.warning("RedisLock acquire error: %s", exc)
                self.acquired = True  # Graceful lock bypass in dev
        else:
            self.acquired = True  # Memory fallback bypass
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.acquired and self.client is not None:
            try:
                await self.client.delete(self.key)
            except Exception as exc:
                logger.warning("RedisLock release error: %s", exc)


class CacheService:
    """Manages cache states using Redis with a robust local memory fallback."""

    def __init__(self) -> None:
        self._redis_client = None
        self._redis_initialized = False

    async def _get_client(self) -> Any | None:
        if self._redis_initialized:
            return self._redis_client
        self._redis_initialized = True
        if not settings.ENABLE_REDIS:
            return None
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await client.ping()
            self._redis_client = client
            logger.info("CacheService: Connected to Redis at %s", settings.REDIS_URL)
        except Exception as exc:
            logger.warning(
                "CacheService: Redis offline (%s), falling back to in-process memory.",
                exc,
            )
            self._redis_client = None
        return self._redis_client

    async def get(self, key: str) -> Any | None:
        """Retrieves raw value from cache, deserializing json payloads."""
        client = await self._get_client()
        if client is not None:
            try:
                val = await client.get(key)
                if val:
                    return json.loads(val)
            except Exception as exc:
                logger.warning("CacheService GET error for key=%s: %s", key, exc)

        # Local fallback lookup
        async with _LOCAL_STORE_LOCK:
            entry = _LOCAL_STORE.get(key)
            if entry:
                val_str, expires_at = entry
                if time.monotonic() < expires_at:
                    return json.loads(val_str)
                else:
                    _LOCAL_STORE.pop(key, None)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Saves target value to cache serializing to JSON format."""
        val_str = json.dumps(value)
        client = await self._get_client()
        if client is not None:
            try:
                await client.set(key, val_str, ex=ttl)
                return
            except Exception as exc:
                logger.warning("CacheService SET error for key=%s: %s", key, exc)

        # Local fallback set
        async with _LOCAL_STORE_LOCK:
            _LOCAL_STORE[key] = (val_str, time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        """Removes a key from cache."""
        client = await self._get_client()
        if client is not None:
            try:
                await client.delete(key)
                return
            except Exception as exc:
                logger.warning("CacheService DELETE error for key=%s: %s", key, exc)

        # Local fallback delete
        async with _LOCAL_STORE_LOCK:
            _LOCAL_STORE.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:
        """Removes all keys matching a wildcard glob pattern."""
        client = await self._get_client()
        if client is not None:
            try:
                keys = await client.keys(pattern)
                if keys:
                    await client.delete(*keys)
                return
            except Exception as exc:
                logger.warning(
                    "CacheService DELETE_PATTERN error for pattern=%s: %s", pattern, exc
                )

        # Local fallback delete matching pattern
        async with _LOCAL_STORE_LOCK:
            prefix = pattern.replace("*", "")
            target_keys = [k for k in _LOCAL_STORE if k.startswith(prefix)]
            for k in target_keys:
                _LOCAL_STORE.pop(k, None)

    @asynccontextmanager
    async def lock(self, key: str, timeout: int = 10) -> AsyncGenerator[RedisLock]:
        """Distributed lock context manager provider."""
        client = await self._get_client()
        async with RedisLock(client, key, timeout) as lock:
            yield lock
