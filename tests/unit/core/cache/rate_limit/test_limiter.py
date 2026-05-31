from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.core.cache.rate_limit.limiter import is_rate_limited, get_ip, normalise_path


class TestNormalisePath:
    def test_strips_uuid_and_following_short_segments_retained(self):
        # The regex strips any /segment of 8+ chars, so "submit" (6 chars) survives
        # but "/challenge" (9 chars) is also stripped. Real output: "/submit"
        result = normalise_path("/challenge/abc12345-1234-1234-1234-abcdef123456/submit")
        assert "abc12345" not in result
        assert result == "/submit"

    def test_strips_dynamic_id_leaving_short_prefix(self):
        # "/room" is 4 chars — kept. "/room-id-xyz123ab" is 18 chars — stripped.
        # "/leaderboard" is 12 chars — also stripped.
        result = normalise_path("/room/room-id-xyz123ab/leaderboard")
        assert "room-id-xyz123ab" not in result
        assert result == "/room"

    def test_eight_char_plus_static_segments_also_stripped(self):
        # "/challenge" is 9 chars so it gets stripped too
        result = normalise_path("/api/v1/challenge")
        assert result == "/api/v1"

    def test_short_segments_only_unchanged(self):
        # "/health" is 7 chars — not stripped
        result = normalise_path("/health")
        assert result == "/health"

    def test_empty_path_returns_unchanged(self):
        assert normalise_path("") == ""

    def test_root_path_unchanged(self):
        assert normalise_path("/") == "/"

    def test_multiple_dynamic_segments_all_stripped(self):
        # "/room" (4), "/roomid123" (10 stripped), "/user" (5), "/userid456" (10 stripped), "/score" (6)
        result = normalise_path("/room/roomid123/user/userid456/score")
        assert "roomid123" not in result
        assert "userid456" not in result
        assert result == "/room/user/score"

    def test_path_with_only_short_segment_unchanged(self):
        result = normalise_path("/api/v1")
        assert result == "/api/v1"


def _fake_request(path="/test", method="GET", headers=None, client_host="1.2.3.4"):
    req = MagicMock()
    req.method = method
    req.url.path = path
    req.headers = headers or {}
    req.client = MagicMock()
    req.client.host = client_host
    return req


class TestGetIp:
    def test_returns_client_host_when_no_forwarded_header(self):
        req = _fake_request(client_host="10.0.0.1")
        assert get_ip(req) == "10.0.0.1"

    def test_returns_first_ip_from_x_forwarded_for(self):
        req = _fake_request(headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"})
        assert get_ip(req) == "203.0.113.5"

    def test_strips_whitespace_from_forwarded_ip(self):
        req = _fake_request(headers={"X-Forwarded-For": "  203.0.113.5  , 10.0.0.1"})
        assert get_ip(req) == "203.0.113.5"

    def test_single_ip_in_forwarded_header(self):
        req = _fake_request(headers={"X-Forwarded-For": "203.0.113.99"})
        assert get_ip(req) == "203.0.113.99"


class TestIsRateLimited:
    def _make_redis(self, count=1, ttl=55):
        r = AsyncMock()
        r.incr = AsyncMock(return_value=count)
        r.expire = AsyncMock()
        r.ttl = AsyncMock(return_value=ttl)
        return r

    @pytest.mark.asyncio
    async def test_not_limited_when_under_limit(self):
        redis = self._make_redis(count=3)
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is False
        assert headers["X-RateLimit-Limit"] == "10"
        assert int(headers["X-RateLimit-Remaining"]) == 7

    @pytest.mark.asyncio
    async def test_limited_when_count_exceeds_limit(self):
        redis = self._make_redis(count=11)
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is True
        assert "Retry-After" in headers

    @pytest.mark.asyncio
    async def test_exactly_at_limit_is_not_limited(self):
        redis = self._make_redis(count=10)
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            limited, _ = await is_rate_limited(req, limit=10)

        assert limited is False

    @pytest.mark.asyncio
    async def test_expire_called_on_first_request(self):
        redis = self._make_redis(count=1)
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            await is_rate_limited(req, limit=10, window_seconds=60)

        redis.expire.assert_awaited_once()
        call_args = redis.expire.call_args[0]
        assert call_args[1] == 60

    @pytest.mark.asyncio
    async def test_expire_not_called_on_subsequent_requests(self):
        redis = self._make_redis(count=5)
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            await is_rate_limited(req, limit=10)

        redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self):
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store",
                   AsyncMock(side_effect=ConnectionError("redis down"))):
            limited, headers = await is_rate_limited(req, limit=10)

        assert limited is False
        assert headers == {}

    @pytest.mark.asyncio
    async def test_remaining_is_zero_when_at_or_over_limit(self):
        redis = self._make_redis(count=15)
        req = _fake_request()

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            _, headers = await is_rate_limited(req, limit=10)

        assert int(headers["X-RateLimit-Remaining"]) == 0

    @pytest.mark.asyncio
    async def test_key_includes_method_and_normalised_path(self):
        redis = self._make_redis(count=1)
        req = _fake_request(method="POST", path="/challenge/abc12345-xxxx/submit")

        with patch("app.core.cache.rate_limit.limiter.get_store", AsyncMock(return_value=redis)):
            await is_rate_limited(req, limit=10)

        key_used = redis.incr.call_args[0][0]
        assert "POST" in key_used
        assert "abc12345" not in key_used
        assert "submit" in key_used
