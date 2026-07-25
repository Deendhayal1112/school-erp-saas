"""
Redis-Backed Sliding-Window Rate Limiting Engine.
"""

import logging
import time

from fastapi import Request

from app.cache.service import CacheService
from app.common.utils import get_client_ip
from app.core.config import settings
from app.exceptions.exceptions import RateLimitExceededException
from app.middleware.request_context import get_request_context

logger = logging.getLogger(__name__)

# Fallback local in-memory sliding window store: key -> list of timestamps
_LOCAL_LIMITS: dict[str, list[float]] = {}


class RateLimiter:
    """FastAPI Dependency for rate limiting requests using Redis sliding window."""

    def __init__(self, limit: int = 100, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.cache_service = CacheService()

    async def __call__(self, request: Request) -> None:
        if not settings.ENABLE_RATE_LIMITING:
            return

        # 1. Determine client identifier context
        ctx = get_request_context()
        if ctx and ctx.user_id:
            identifier = f"user:{ctx.user_id}"
        elif ctx and ctx.school_id:
            identifier = f"school:{ctx.school_id}"
        else:
            identifier = f"ip:{get_client_ip(request)}"

        # Clean endpoint name to avoid collisions
        endpoint_name = request.scope.get("endpoint").__name__ if request.scope.get("endpoint") else "global"
        key = f"rate_limit:{endpoint_name}:{identifier}"

        now = time.time()
        client = await self.cache_service._get_client()

        if client is not None:
            try:
                # Sliding window algorithm using Redis Sorted Sets (ZSET)
                # Remove expired logs, add current log, count size, expire key
                pipe = client.pipeline()
                clear_before = now - self.window_seconds

                pipe.zremrangebyscore(key, "-inf", clear_before)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, self.window_seconds)

                # Execute pipeline
                _, current_count, _, _ = await pipe.execute()

                if current_count >= self.limit:
                    logger.warning("Rate limit exceeded for client %s on %s: %d/%d", identifier, endpoint_name, current_count, self.limit)
                    raise RateLimitExceededException(
                        message=f"Rate limit exceeded. Maximum allowed: {self.limit} requests per {self.window_seconds}s."
                    )
                return
            except RateLimitExceededException:
                raise
            except Exception as exc:
                logger.warning("Redis rate limiter error: %s. Falling back to local memory limit.", exc)

        # 2. Local memory fallback sliding window
        logger.debug("Executing local memory rate limit fallback for key=%s", key)
        clear_before = now - self.window_seconds

        # Get timestamps and filter expired ones
        timestamps = _LOCAL_LIMITS.get(key, [])
        timestamps = [t for t in timestamps if t > clear_before]

        if len(timestamps) >= self.limit:
            raise RateLimitExceededException(
                message=f"Rate limit exceeded (fallback). Maximum allowed: {self.limit} requests per {self.window_seconds}s."
            )

        timestamps.append(now)
        _LOCAL_LIMITS[key] = timestamps
