"""
Tests for Sliding-Window Rate Limiting Engine.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.exceptions.exceptions import RateLimitExceededException
from app.rate_limit.limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_and_blocks():
    # Set small limit to trigger lockout quickly
    limiter = RateLimiter(limit=3, window_seconds=10)

    # Mock request
    mock_request = MagicMock(spec=Request)
    mock_request.scope = {"endpoint": lambda: None}
    mock_request.headers = {}
    mock_request.client = MagicMock()
    mock_request.client.host = "192.168.1.100"

    # Delete key first to ensure a clean window
    client = await limiter.cache_service._get_client()
    if client:
        await client.delete("rate_limit:<lambda>:ip:192.168.1.100")

    from app.core.config import settings

    original_val = settings.ENABLE_RATE_LIMITING
    settings.ENABLE_RATE_LIMITING = True

    try:
        # 1. First 3 requests should pass without exceptions
        await limiter(mock_request)
        await limiter(mock_request)
        await limiter(mock_request)

        # 2. 4th request should raise RateLimitExceededException (429 status code)
        with pytest.raises(RateLimitExceededException) as exc:
            await limiter(mock_request)
        assert exc.value.status_code == 429
        assert "rate limit exceeded" in str(exc.value.message).lower()
    finally:
        settings.ENABLE_RATE_LIMITING = original_val
