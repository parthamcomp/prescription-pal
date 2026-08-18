"""Tier 1 unit tests for app/services/rate_limit.py.

Contains the FAILURE-INJECTION reference implementation: for every
integration point (Redis here), assert graceful degradation - a limiter
outage must never turn into a 500 or block traffic, per rate_limit.py's own
documented contract ("Fails open... a limiter outage doesn't take the API
down").
"""
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.rate_limit import _check


# --------------------------------------------------------------------------
# FAILURE-INJECTION REFERENCE IMPLEMENTATION
# Pattern: replace the integration point with a double that fails the exact
# way the real dependency fails (connection refused, timeout, malformed
# response, ...) and assert the caller degrades gracefully - never a stack
# trace, never blocked traffic for an outage that isn't the caller's fault.
# --------------------------------------------------------------------------
class TestRateLimitFailsOpenOnRedisOutage:
    async def test_connection_error_does_not_block_the_request(self, monkeypatch):
        broken_client = AsyncMock()
        broken_client.incr.side_effect = RedisConnectionError("connection refused")
        monkeypatch.setattr("app.services.rate_limit._client", lambda: broken_client)

        # Must not raise - a Redis outage must never surface as a 500, and
        # must never itself block a request that has nothing to do with it.
        await _check("test_bucket", "some-identity", limit=1, window_seconds=60)

    async def test_timeout_does_not_block_the_request(self, monkeypatch):
        broken_client = AsyncMock()
        broken_client.incr.side_effect = TimeoutError("redis timed out")
        monkeypatch.setattr("app.services.rate_limit._client", lambda: broken_client)

        await _check("test_bucket", "some-identity", limit=1, window_seconds=60)


class TestRateLimitEnforcement:
    async def test_allows_requests_under_the_limit(self, fake_redis):
        for _ in range(3):
            await _check("bucket_a", "user-1", limit=3, window_seconds=60)
        # No exception across 3 calls with limit=3 - the third call lands
        # exactly on the boundary (count == limit) and must still pass.

    async def test_rejects_the_request_that_exceeds_the_limit(self, fake_redis):
        for _ in range(3):
            await _check("bucket_b", "user-2", limit=3, window_seconds=60)

        with pytest.raises(HTTPException) as exc_info:
            await _check("bucket_b", "user-2", limit=3, window_seconds=60)

        assert exc_info.value.status_code == 429

    async def test_different_identities_have_independent_limits(self, fake_redis):
        for _ in range(3):
            await _check("bucket_c", "user-3", limit=3, window_seconds=60)

        # A different identity in the same bucket must not inherit user-3's
        # exhausted count.
        await _check("bucket_c", "user-4", limit=3, window_seconds=60)
