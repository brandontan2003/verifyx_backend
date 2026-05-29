from datetime import date

from fastapi import Request

from app.config import settings
from app.core.exceptions.exceptions import RateLimitExceededException, DailyChallengeLimitException
from app.core.logger import logger
from app.core.rate_limit.limiter import is_rate_limited
from app.core.rate_limit.redis_store import get_redis


async def ai_rate_limit(request: Request):
    """10 req/min — POST /challenge and POST /challenge/{id}/submit"""
    limited, headers = await is_rate_limited(request, limit=settings.RATE_LIMIT_AI)
    if limited:
        raise RateLimitExceededException(headers)
    return None


async def auth_rate_limit(request: Request):
    """10 req/min — signin, signup, forget/update password"""
    limited, headers = await is_rate_limited(request, limit=settings.RATE_LIMIT_AUTH)
    if limited:
        raise RateLimitExceededException(headers)
    return None


async def room_rate_limit(request: Request):
    """20 req/min — POST /room, /room/join, /room/{id}/start"""
    limited, headers = await is_rate_limited(request, limit=settings.RATE_LIMIT_ROOM)
    if limited:
        raise RateLimitExceededException(headers)
    return None


async def read_rate_limit(request: Request):
    """60 req/min — all GET endpoints"""
    limited, headers = await is_rate_limited(request, limit=settings.RATE_LIMIT_READ)
    if limited:
        raise RateLimitExceededException(headers)
    return None


async def submit_rate_limit(request: Request):
    """60 req/min — all POST & PUT endpoints"""
    limited, headers = await is_rate_limited(request, limit=settings.RATE_LIMIT_SUBMIT)
    if limited:
        raise RateLimitExceededException(headers)
    return None


def _daily_key(user_id: str) -> str:
    return f"daily_challenge:{user_id}:{date.today().isoformat()}"


async def _check_daily_limit(user_id: str) -> None:
    try:
        redis = await get_redis()
        count = await redis.get(_daily_key(user_id))
        if count is not None and int(count) >= settings.DAILY_CHALLENGE_LIMIT:
            raise DailyChallengeLimitException()
    except DailyChallengeLimitException:
        raise
    except Exception as exc:
        logger.warning("daily_limit check Redis error — failing open for user %s: %s", user_id, exc)


async def _increment_daily_limit(user_id: str) -> None:
    try:
        redis = await get_redis()
        key = _daily_key(user_id)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 172800)  # 48h — survives midnight safely
    except Exception as exc:
        logger.warning("daily_limit increment Redis error for user %s: %s", user_id, exc)
