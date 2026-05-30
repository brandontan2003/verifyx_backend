import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from app.core.cache.registry import InMemoryStore, RedisStore


# ---------------------------------------------------------------------------
# InMemoryStore
# ---------------------------------------------------------------------------

class TestInMemoryStore:

    @pytest.fixture
    def store(self):
        return InMemoryStore()

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self, store):
        assert await store.get("no-such-key") is None

    @pytest.mark.asyncio
    async def test_incr_creates_key_at_1(self, store):
        count = await store.incr("k")
        assert count == 1

    @pytest.mark.asyncio
    async def test_incr_increments_existing_key(self, store):
        await store.incr("k")
        await store.incr("k")
        count = await store.incr("k")
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_returns_bytes_after_incr(self, store):
        await store.incr("k")
        value = await store.get("k")
        assert value == b"1"

    @pytest.mark.asyncio
    async def test_expire_sets_ttl(self, store):
        await store.incr("k")
        await store.expire("k", 60)
        ttl = await store.ttl("k")
        assert 58 <= ttl <= 60  # allow 2s test jitter

    @pytest.mark.asyncio
    async def test_ttl_returns_negative_one_without_expire(self, store):
        await store.incr("k")
        assert await store.ttl("k") == -1

    @pytest.mark.asyncio
    async def test_expired_key_get_returns_none(self, store):
        await store.incr("k")
        await store.expire("k", 1)
        # Manually wind back the clock on the stored entry
        store._data["k"] = (1, time.monotonic() - 1)
        assert await store.get("k") is None

    @pytest.mark.asyncio
    async def test_expired_key_incr_resets_to_1(self, store):
        await store.incr("k")
        store._data["k"] = (5, time.monotonic() - 1)  # force expiry
        count = await store.incr("k")
        assert count == 1

    @pytest.mark.asyncio
    async def test_expire_on_missing_key_is_noop(self, store):
        # Should not raise
        await store.expire("nonexistent", 60)
        assert await store.ttl("nonexistent") == -1

    @pytest.mark.asyncio
    async def test_incr_preserves_existing_ttl(self, store):
        await store.incr("k")
        await store.expire("k", 60)
        await store.incr("k")  # second increment must not wipe TTL
        ttl = await store.ttl("k")
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_close_is_safe(self, store):
        await store.close()  # must not raise

    @pytest.mark.asyncio
    async def test_concurrent_incr_is_consistent(self, store):
        """100 concurrent incr() calls on the same key must all be serialised."""
        results = await asyncio.gather(*[store.incr("k") for _ in range(100)])
        assert sorted(results) == list(range(1, 101))
        assert await store.get("k") == b"100"


# ---------------------------------------------------------------------------
# RedisStore
# ---------------------------------------------------------------------------

class TestRedisStore:

    def _make_client(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=b"3")
        client.incr = AsyncMock(return_value=4)
        client.expire = AsyncMock(return_value=True)
        client.ttl = AsyncMock(return_value=45)
        client.aclose = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_delegates_to_client(self):
        client = self._make_client()
        store = RedisStore(client)
        result = await store.get("k")
        client.get.assert_called_once_with("k")
        assert result == b"3"

    @pytest.mark.asyncio
    async def test_incr_delegates_to_client(self):
        client = self._make_client()
        store = RedisStore(client)
        result = await store.incr("k")
        client.incr.assert_called_once_with("k")
        assert result == 4

    @pytest.mark.asyncio
    async def test_expire_delegates_to_client(self):
        client = self._make_client()
        store = RedisStore(client)
        await store.expire("k", 30)
        client.expire.assert_called_once_with("k", 30)

    @pytest.mark.asyncio
    async def test_ttl_delegates_to_client(self):
        client = self._make_client()
        store = RedisStore(client)
        result = await store.ttl("k")
        client.ttl.assert_called_once_with("k")
        assert result == 45

    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        client = self._make_client()
        store = RedisStore(client)
        await store.close()
        client.aclose.assert_called_once()
