"""
Token bucket rate limiter backed by Redis.

Key format: ratelimit:{ip}:{normalised_route}
TTL = window_seconds (auto-expires, no manual cleanup needed)

Normalisation strips dynamic path segments so that:
  POST /challenge/abc-123/submit  →  POST:/challenge/submit
  GET  /room/xyz-456/leaderboard  →  GET:/room/leaderboard
  GET  /room/xyz-456/challenge    →  GET:/room/challenge

This means every submission attempt from an IP shares one counter
regardless of which challenge_id is targeted — which is what we want.
"""
import re
import time

from fastapi import Request

from app.core.logger import logger
from app.core.rate_limit.redis_store import get_redis

# Regex to strip UUIDs and other dynamic segments (alphanumeric + hyphens, 8+ chars)
_DYNAMIC_SEGMENT = re.compile(r"/[a-zA-Z0-9_-]{8,}")


def normalise_path(path: str) -> str:
    """Strip dynamic path segments to produce a stable route key."""
    return _DYNAMIC_SEGMENT.sub("", path) or path


def get_ip(request: Request) -> str:
    """
    Extract real client IP.
    Checks X-Forwarded-For first (set by Railway / AWS ALB proxies),
    falls back to direct connection IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


async def is_rate_limited(
        request: Request,
        limit: int,
        window_seconds: int = 60
) -> tuple[bool, dict]:
    """
    Token bucket check via Redis INCR + EXPIRE.

    Returns:
        (limited: bool, headers: dict)
        headers contains X-RateLimit-* values for the response.

    If Redis is unreachable, fails open (allows the request) and logs a warning.
    Failing open is the correct choice — a Redis outage should not take down the app.
    """
    ip = get_ip(request)
    route = f"{request.method}:{normalise_path(request.url.path)}"
    key = f"ratelimit:{ip}:{route}"

    try:
        redis = await get_redis()

        # Atomic increment + set TTL on first call
        # INCR is atomic — safe across multiple FastAPI instances
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)

        ttl = await redis.ttl(key)
        remaining = max(0, limit - count)

        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(time.time()) + ttl),
        }

        if count > limit:
            headers["Retry-After"] = str(ttl)
            return True, headers

        return False, headers

    except Exception as exc:
        logger.warning(
            "Rate limiter Redis error — failing open for %s %s: %s",
            request.method, request.url.path, exc
        )
        return False, {}
