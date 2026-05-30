import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request
from starlette.datastructures import Headers

from app.core.cache.rate_limit.dependencies import (
    ai_rate_limit,
    auth_rate_limit,
    room_rate_limit,
    read_rate_limit,
    submit_rate_limit,
)
from app.core.cache.rate_limit.limiter import normalise_path, get_ip, is_rate_limited
from app.core.exceptions.exceptions import RateLimitExceededException


def _make_request(path: str = "/submit", method: str = "POST", client_host: str = "1.2.3.4",
                  forwarded_for: str | None = None) -> Request:
    """Build a minimal Starlette Request stub."""
    headers = {}
    if forwarded_for:
        headers["x-forwarded-for"] = forwarded_for

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": Headers(headers=headers).raw,
        # Starlette reads client from scope["client"] as a (host, port) tuple
        "client": (client_host, 9999),
    }
    return Request(scope)


def _mock_redis(current_count: int = 1, ttl: int = 55) -> AsyncMock:
    """Return a Redis mock pre-configured with given count and ttl."""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=current_count)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=ttl)
    return redis


class TestNormalisePath:
    # NOTE: The regex _DYNAMIC_SEGMENT strips ANY path segment >= 8 chars,
    # which includes static route names like /challenge (9), /leaderboard (11),
    # /progress (8). This is a known limitation of the current implementation —
    # it produces stable keys but at the cost of over-collapsing some routes.
    # These tests document the ACTUAL behaviour so regressions are caught.

    def test_strips_dynamic_id_from_two_segment_path(self):
        # /challenge (9 chars) is also stripped, leaving only /submit
        assert normalise_path("/challenge/abc-12345/submit") == "/submit"

    def test_strips_all_long_segments(self):
        # Both room (4, kept) and /xyz-456abc (dynamic, stripped)
        # /challenge (9, stripped) and /abc-12345 (dynamic, stripped)
        assert normalise_path("/room/xyz-456abc/challenge/abc-12345") == "/room"

    def test_preserves_short_segments(self):
        # Segments < 8 chars are never stripped
        assert normalise_path("/room/join") == "/room/join"
        assert normalise_path("/auth/user") == "/auth/user"

    def test_empty_result_falls_back_to_original(self):
        # If stripping would produce empty string, original path is returned
        result = normalise_path("/abcdefghij")  # whole path is one long segment
        assert result == "/abcdefghij"

    def test_preserves_root(self):
        assert normalise_path("/") == "/"

    def test_mixed_static_and_dynamic(self):
        # /room (4, kept), /xyz-456abc (dynamic, stripped), /leaderboard (11, stripped)
        assert normalise_path("/room/xyz-456abc/leaderboard") == "/room"

    def test_short_route_with_no_ids_unchanged(self):
        assert normalise_path("/room/join") == "/room/join"
        assert normalise_path("/auth/user") == "/auth/user"


class TestGetIp:
    def test_returns_direct_client_ip_when_no_header(self):
        req = _make_request(client_host="10.0.0.1")
        assert get_ip(req) == "10.0.0.1"

    def test_returns_first_forwarded_ip(self):
        req = _make_request(forwarded_for="5.6.7.8, 192.168.1.1")
        assert get_ip(req) == "5.6.7.8"

    def test_strips_whitespace_from_forwarded_ip(self):
        req = _make_request(forwarded_for="  9.9.9.9 , 1.1.1.1")
        assert get_ip(req) == "9.9.9.9"

    def test_single_forwarded_ip(self):
        req = _make_request(forwarded_for="203.0.113.42")
        assert get_ip(req) == "203.0.113.42"


class TestIsRateLimited:

    @pytest.mark.asyncio
    async def test_first_request_not_limited(self):
        redis = _mock_redis(current_count=1)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is False
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "9"

    @pytest.mark.asyncio
    async def test_at_exact_limit_not_limited(self):
        """count == limit → still allowed (limit is the ceiling, >limit triggers 429)."""
        redis = _mock_redis(current_count=10)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is False
        assert headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_over_limit_is_limited(self):
        redis = _mock_redis(current_count=11)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is True
        assert "Retry-After" in headers

    @pytest.mark.asyncio
    async def test_remaining_never_goes_negative(self):
        redis = _mock_redis(current_count=999)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            limited, headers = await is_rate_limited(req, limit=10)

        assert int(headers["X-RateLimit-Remaining"]) == 0

    @pytest.mark.asyncio
    async def test_expire_called_only_on_first_increment(self):
        """TTL should only be set when count == 1 (first request in window)."""
        redis = _mock_redis(current_count=1)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            await is_rate_limited(req, limit=10)

        redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_expire_not_called_on_subsequent_increments(self):
        redis = _mock_redis(current_count=5)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            await is_rate_limited(req, limit=10)

        redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_key_includes_ip_method_and_normalised_path(self):
        redis = _mock_redis()
        # Use /room/join (both segments < 8 chars, nothing stripped) for a predictable key
        req = _make_request(path="/room/join", method="GET", client_host="1.2.3.4")

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            await is_rate_limited(req, limit=10)

        called_key = redis.incr.call_args[0][0]
        assert called_key == "ratelimit:1.2.3.4:GET:/room/join"

    @pytest.mark.asyncio
    async def test_reset_header_is_future_timestamp(self):
        ttl = 45
        redis = _mock_redis(ttl=ttl)
        req = _make_request()

        before = int(time.time())
        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            _, headers = await is_rate_limited(req, limit=10)

        reset = int(headers["X-RateLimit-Reset"])
        assert reset >= before + ttl

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self):
        """Redis outage must not block requests — fails open, returns empty headers."""
        redis = AsyncMock()
        redis.incr.side_effect = ConnectionError("Redis down")

        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is False
        assert headers == {}

    @pytest.mark.asyncio
    async def test_custom_window_seconds_passed_to_expire(self):
        redis = _mock_redis(current_count=1)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            await is_rate_limited(req, limit=10, window_seconds=120)

        from unittest.mock import ANY
        redis.expire.assert_called_once_with(ANY, 120)

    @pytest.mark.asyncio
    async def test_different_ips_get_separate_counters(self):
        """Two requests from different IPs must hit different Redis keys."""
        redis = _mock_redis()

        req_a = _make_request(client_host="1.1.1.1")
        req_b = _make_request(client_host="2.2.2.2")

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis):
            await is_rate_limited(req_a, limit=10)
            await is_rate_limited(req_b, limit=10)

        keys_called = [call[0][0] for call in redis.incr.call_args_list]
        assert keys_called[0] != keys_called[1]
        assert "1.1.1.1" in keys_called[0]
        assert "2.2.2.2" in keys_called[1]


class TestRateLimitDependencies:
    """
    Each dependency (ai_rate_limit, auth_rate_limit, etc.) must:
      - Pass through when not limited
      - Raise RateLimitExceededException when limited
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dep_fn,limit_setting", [
        (ai_rate_limit, "RATE_LIMIT_AI"),
        (auth_rate_limit, "RATE_LIMIT_AUTH"),
        (room_rate_limit, "RATE_LIMIT_ROOM"),
        (read_rate_limit, "RATE_LIMIT_READ"),
        (submit_rate_limit, "RATE_LIMIT_SUBMIT"),
    ])
    async def test_passes_when_not_limited(self, dep_fn, limit_setting):
        redis = _mock_redis(current_count=1)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis), \
                patch("app.core.cache.rate_limit.dependencies.settings") as mock_settings:
            setattr(mock_settings, limit_setting, 10)
            result = await dep_fn(req)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dep_fn,limit_setting", [
        (ai_rate_limit, "RATE_LIMIT_AI"),
        (auth_rate_limit, "RATE_LIMIT_AUTH"),
        (room_rate_limit, "RATE_LIMIT_ROOM"),
        (read_rate_limit, "RATE_LIMIT_READ"),
        (submit_rate_limit, "RATE_LIMIT_SUBMIT"),
    ])
    async def test_raises_when_limited(self, dep_fn, limit_setting):
        redis = _mock_redis(current_count=999)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis), \
                patch("app.core.cache.rate_limit.dependencies.settings") as mock_settings:
            setattr(mock_settings, limit_setting, 10)

            with pytest.raises(RateLimitExceededException) as exc_info:
                await dep_fn(req)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_exception_carries_retry_after_header(self):
        redis = _mock_redis(current_count=999, ttl=30)
        req = _make_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", return_value=redis), \
                patch("app.core.cache.rate_limit.dependencies.settings") as mock_settings:
            mock_settings.RATE_LIMIT_AUTH = 5

            with pytest.raises(RateLimitExceededException) as exc_info:
                await auth_rate_limit(req)

        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "30"
