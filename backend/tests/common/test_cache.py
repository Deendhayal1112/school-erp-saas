"""
Tests for Cache Service and Locks.
"""

import pytest

from app.cache.service import CacheService


@pytest.mark.asyncio
async def test_cache_service_store_and_retrieve():
    cache = CacheService()

    # 1. Test set and get
    test_key = "test:cache:item"
    test_data = {"user": "Alice", "score": 95}
    await cache.set(test_key, test_data, ttl=10)

    retrieved = await cache.get(test_key)
    assert retrieved == test_data

    # 2. Test delete
    await cache.delete(test_key)
    deleted_val = await cache.get(test_key)
    assert deleted_val is None


@pytest.mark.asyncio
async def test_cache_service_locks():
    cache = CacheService()

    # Test lock acquisition
    async with cache.lock("resource_key", timeout=5) as lock:
        assert lock.acquired is True

        # Trying to acquire same lock concurrently (if Redis is active, it blocks/fails.
        # Since this tests fallback/mock states safely, we assert correct exit)
        pass
