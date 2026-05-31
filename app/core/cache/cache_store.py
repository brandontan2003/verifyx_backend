"""
Initialised by main.py at startup via init_store().
Use get_store() everywhere instead of importing the store directly.
"""
from app.core.cache.registry import RateLimitStore

_store: RateLimitStore | None = None


def init_store(store: RateLimitStore) -> None:
    global _store
    _store = store


async def get_store() -> RateLimitStore:
    if _store is None:
        raise RuntimeError("RateLimitStore not initialised — call init_store() at startup")
    return _store


async def close_store() -> None:
    global _store
    if _store:
        await _store.close()
        _store = None
