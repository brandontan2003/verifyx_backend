from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache.rate_limit.dependencies import _check_daily_limit, _daily_key, _increment_daily_limit


class TestDailyKey:
    def test_key_contains_user_id(self):
        key = _daily_key("user-42")
        assert "user-42" in key

    def test_key_contains_todays_date(self):
        key = _daily_key("user-1")
        assert date.today().isoformat() in key

    def test_key_format_is_stable(self):
        key = _daily_key("u1")
        assert key.startswith("daily_challenge:u1:")

    def test_different_users_get_different_keys(self):
        assert _daily_key("user-A") != _daily_key("user-B")


class TestCheckDailyLimit:
    @pytest.mark.asyncio
    async def test_does_not_raise_when_under_limit(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"4")

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)), \
                patch("app.core.cache.rate_limit.dependencies.settings") as s:
            s.DAILY_CHALLENGE_LIMIT = 10
            await _check_daily_limit("user-1")  # should not raise

    @pytest.mark.asyncio
    async def test_raises_when_at_limit(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"10")

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)), \
                patch("app.core.cache.rate_limit.dependencies.settings") as s:
            s.DAILY_CHALLENGE_LIMIT = 10
            from app.core.exceptions.exceptions import DailyChallengeLimitException
            with pytest.raises(DailyChallengeLimitException):
                await _check_daily_limit("user-1")

    @pytest.mark.asyncio
    async def test_does_not_raise_when_key_absent(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)), \
                patch("app.core.cache.rate_limit.dependencies.settings") as s:
            s.DAILY_CHALLENGE_LIMIT = 10
            await _check_daily_limit("user-1")  # should not raise

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self):
        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(side_effect=ConnectionError("down"))):
            await _check_daily_limit("user-1")  # must not raise

    @pytest.mark.asyncio
    async def test_raises_when_count_exceeds_limit(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"15")

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)), \
                patch("app.core.cache.rate_limit.dependencies.settings") as s:
            s.DAILY_CHALLENGE_LIMIT = 10
            from app.core.exceptions.exceptions import DailyChallengeLimitException
            with pytest.raises(DailyChallengeLimitException):
                await _check_daily_limit("user-1")


class TestIncrementDailyLimit:
    @pytest.mark.asyncio
    async def test_increments_key(self):
        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)):
            await _increment_daily_limit("user-1")

        redis.incr.assert_awaited_once()
        key_used = redis.incr.call_args[0][0]
        assert "user-1" in key_used

    @pytest.mark.asyncio
    async def test_sets_ttl_on_first_increment(self):
        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)):
            await _increment_daily_limit("user-1")

        redis.expire.assert_awaited_once()
        _, ttl = redis.expire.call_args[0]
        assert ttl == 172800  # 48 hours

    @pytest.mark.asyncio
    async def test_does_not_reset_ttl_on_subsequent_increments(self):
        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=5)
        redis.expire = AsyncMock()

        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(return_value=redis)):
            await _increment_daily_limit("user-1")

        redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self):
        with patch("app.core.cache.rate_limit.dependencies.get_store",
                   AsyncMock(side_effect=ConnectionError("down"))):
            await _increment_daily_limit("user-1")  # must not raise
