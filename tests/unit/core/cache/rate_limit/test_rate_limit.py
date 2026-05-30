from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.core.cache.rate_limit.dependencies import auth_rate_limit, room_rate_limit, ai_rate_limit, read_rate_limit, \
    submit_rate_limit


def _fake_request(path="/test", method="GET", headers=None, client_host="1.2.3.4"):
    req = MagicMock()
    req.method = method
    req.url.path = path
    req.headers = headers or {}
    req.client = MagicMock()
    req.client.host = client_host
    return req


class TestRateLimitDependencies:
    @pytest.mark.asyncio
    async def test_ai_rate_limit_raises_when_limited(self):
        req = _fake_request()
        with patch("app.core.cache.rate_limit.dependencies.is_rate_limited",
                   AsyncMock(return_value=(True, {"Retry-After": "60"}))):
            from app.core.exceptions.exceptions import RateLimitExceededException
            with pytest.raises(RateLimitExceededException):
                await ai_rate_limit(req)

    @pytest.mark.asyncio
    async def test_ai_rate_limit_passes_when_not_limited(self):
        req = _fake_request()
        with patch("app.core.cache.rate_limit.dependencies.is_rate_limited",
                   AsyncMock(return_value=(False, {}))):
            result = await ai_rate_limit(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_auth_rate_limit_raises_when_limited(self):
        req = _fake_request()
        with patch("app.core.cache.rate_limit.dependencies.is_rate_limited",
                   AsyncMock(return_value=(True, {}))):
            from app.core.exceptions.exceptions import RateLimitExceededException
            with pytest.raises(RateLimitExceededException):
                await auth_rate_limit(req)

    @pytest.mark.asyncio
    async def test_room_rate_limit_raises_when_limited(self):
        req = _fake_request()
        with patch("app.core.cache.rate_limit.dependencies.is_rate_limited",
                   AsyncMock(return_value=(True, {}))):
            from app.core.exceptions.exceptions import RateLimitExceededException
            with pytest.raises(RateLimitExceededException):
                await room_rate_limit(req)

    @pytest.mark.asyncio
    async def test_read_rate_limit_passes_when_not_limited(self):
        req = _fake_request()
        with patch("app.core.cache.rate_limit.dependencies.is_rate_limited",
                   AsyncMock(return_value=(False, {}))):
            result = await read_rate_limit(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_submit_rate_limit_raises_when_limited(self):
        req = _fake_request()
        with patch("app.core.cache.rate_limit.dependencies.is_rate_limited",
                   AsyncMock(return_value=(True, {}))):
            from app.core.exceptions.exceptions import RateLimitExceededException
            with pytest.raises(RateLimitExceededException):
                await submit_rate_limit(req)
