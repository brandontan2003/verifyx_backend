"""
Redis connection for rate limiting.
Uses a single shared async connection pool across all instances.
"""
_redis = None


def init_redis(redis_client):
    global _redis
    _redis = redis_client


async def get_redis():
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
