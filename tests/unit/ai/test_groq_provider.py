from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.providers.groq import GroqProvider


def _mock_groq_response(content: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    resp.raise_for_status = MagicMock(
        side_effect=None if status_code == 200
        else Exception(f"HTTP {status_code}")
    )
    return resp


def _patch_httpx(response: MagicMock):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_ctx
    return mock_httpx, mock_client


class TestGroqProviderComplete:

    @pytest.mark.asyncio
    async def test_returns_content_from_choices(self):
        mock_httpx, _ = _patch_httpx(_mock_groq_response('{"verdict": "scam"}'))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            result = await GroqProvider().complete("system", "user", 512)
        assert result == '{"verdict": "scam"}'

    @pytest.mark.asyncio
    async def test_posts_to_correct_groq_url(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 64)
        url = mock_client.post.call_args.args[0]
        assert url == "https://api.groq.com/openai/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_request_payload_has_system_and_user_messages(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("my system", "my user", 128)
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["messages"][0] == {"role": "system", "content": "my system"}
        assert payload["messages"][1] == {"role": "user", "content": "my user"}

    @pytest.mark.asyncio
    async def test_request_payload_has_correct_model_from_settings(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "mixtral-8x7b-32768"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 64)
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["model"] == "mixtral-8x7b-32768"

    @pytest.mark.asyncio
    async def test_request_payload_has_max_completion_tokens(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 256)
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["max_completion_tokens"] == 256

    @pytest.mark.asyncio
    async def test_request_payload_has_stream_false(self):
        """Streaming must be disabled — the response is consumed as a single JSON object."""
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 64)
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["stream"] is False

    @pytest.mark.asyncio
    async def test_request_payload_stop_sequence_is_backtick_fence(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 64)
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["stop"] == "```"

    @pytest.mark.asyncio
    async def test_authorization_header_contains_api_key(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "gsk-secret-key"
            await GroqProvider().complete("s", "u", 64)
        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer gsk-secret-key"

    @pytest.mark.asyncio
    async def test_content_type_header_is_json(self):
        mock_httpx, mock_client = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 64)
        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_client_initialised_with_30s_timeout(self):
        mock_httpx, _ = _patch_httpx(_mock_groq_response("{}"))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            await GroqProvider().complete("s", "u", 64)
        assert mock_httpx.AsyncClient.call_args.kwargs["timeout"] == 30

    @pytest.mark.asyncio
    async def test_raise_for_status_called(self):
        """Non-200 response must raise — raise_for_status must be called."""
        resp = _mock_groq_response("", status_code=429)
        mock_httpx, _ = _patch_httpx(resp)
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            with pytest.raises(Exception):
                await GroqProvider().complete("s", "u", 64)
        resp.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        mock_httpx, _ = _patch_httpx(_mock_groq_response("", status_code=500))
        with patch("app.ai.providers.groq.httpx", mock_httpx), \
                patch("app.ai.providers.groq.settings") as s:
            s.GROQ_MODEL = "llama-3.3-70b-versatile"
            s.GROQ_API_KEY = "test-key"
            with pytest.raises(Exception):
                await GroqProvider().complete("s", "u", 64)

    def test_provider_name_is_groq(self):
        assert GroqProvider().name == "groq"

    def test_is_ai_provider_subclass(self):
        from app.ai.base import AIProvider
        assert issubclass(GroqProvider, AIProvider)
