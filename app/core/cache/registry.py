import asyncio
import time
from abc import ABC, abstractmethod


class RateLimitStore(ABC):
    """Minimal key-value interface required by the rate limiter."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Return the current raw value for *key*, or None if absent/expired."""
        ...

    @abstractmethod
    async def incr(self, key: str) -> int:
        """Atomically increment *key* and return the new value."""
        ...

    @abstractmethod
    async def expire(self, key: str, seconds: int) -> None:
        """Set TTL on *key*. No-op if key does not exist."""
        ...

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """Return remaining TTL in seconds. Returns -1 if key has no TTL."""
        ...


class RedisStore(RateLimitStore):
    """Thin wrapper around an aioredis client."""

    def __init__(self, client):
        self._client = client

    async def get(self, key: str) -> bytes | None:
        return await self._client.get(key)

    async def incr(self, key: str) -> int:
        return await self._client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        await self._client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        return await self._client.ttl(key)

    async def close(self) -> None:
        await self._client.aclose()


class InMemoryStore(RateLimitStore):
    """
    Single-process in-memory store.

    Thread-safety: asyncio.Lock guards mutations so concurrent coroutines
    within the same event loop are safe. Not safe across OS threads.
    """

    def __init__(self):
        # { key: (value: int, expires_at: float | None) }
        self._data: dict[str, tuple[int, float | None]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, key: str) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return True
        _, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            return True
        return False

    async def get(self, key: str) -> bytes | None:
        async with self._lock:
            if self._is_expired(key):
                self._data.pop(key, None)
                return None
            value, _ = self._data[key]
            return str(value).encode()

    async def incr(self, key: str) -> int:
        async with self._lock:
            if self._is_expired(key):
                # Preserve TTL from the existing (now-expired) entry if any,
                # otherwise no TTL until expire() is called.
                self._data[key] = (1, None)
                return 1
            value, expires_at = self._data[key]
            new_value = value + 1
            self._data[key] = (new_value, expires_at)
            return new_value

    async def expire(self, key: str, seconds: int) -> None:
        async with self._lock:
            if key not in self._data or self._is_expired(key):
                return
            value, _ = self._data[key]
            self._data[key] = (value, time.monotonic() + seconds)

    async def ttl(self, key: str) -> int:
        async with self._lock:
            if self._is_expired(key):
                return -1
            _, expires_at = self._data[key]
            if expires_at is None:
                return -1
            remaining = expires_at - time.monotonic()
            return max(0, int(remaining))

    async def close(self) -> None:
        pass  # Nothing to close
