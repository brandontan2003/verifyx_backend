from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.ai.providers.claude as claude_module
from app.ai.providers.claude import ClaudeProvider


def _make_sdk_response(text: str) -> MagicMock:
    """Build a minimal mock of the Anthropic Message object."""
    text_block = MagicMock()
    text_block.text = text
    response = MagicMock()
    response.content = [text_block]
    return response


@pytest.fixture(autouse=True)
def reset_claude_singleton():
    """Reset the module-level _client singleton before each test."""
    original = claude_module._client
    claude_module._client = None
    yield
    claude_module._client = original


class TestClaudeProviderComplete:

    def _make_mock_anthropic(self, response_text: str):
        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(return_value=_make_sdk_response(response_text))
        mock_client = MagicMock()
        mock_client.messages = mock_messages
        mock_anthropic_cls = MagicMock(return_value=mock_client)
        return mock_anthropic_cls, mock_client, mock_messages

    @pytest.mark.asyncio
    async def test_returns_text_from_first_content_block(self):
        mock_cls, _, _ = self._make_mock_anthropic('{"verdict": "scam"}')
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            result = await ClaudeProvider().complete("system", "user", 512)
        assert result == '{"verdict": "scam"}'

    @pytest.mark.asyncio
    async def test_passes_correct_model_from_settings(self):
        mock_cls, _, mock_messages = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-opus-4-6"
            await ClaudeProvider().complete("system", "user", 256)
        call_kwargs = mock_messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"

    @pytest.mark.asyncio
    async def test_passes_system_and_user_messages(self):
        mock_cls, _, mock_messages = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            await ClaudeProvider().complete("my system prompt", "my user message", 128)
        call_kwargs = mock_messages.create.call_args.kwargs
        assert call_kwargs["system"] == "my system prompt"
        assert call_kwargs["messages"][0]["content"] == "my user message"
        assert call_kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_passes_max_tokens(self):
        mock_cls, _, mock_messages = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            await ClaudeProvider().complete("s", "u", 1024)
        call_kwargs = mock_messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_stop_sequences_contains_backtick_fence(self):
        """Ensures the AI cannot close a markdown code block mid-response."""
        mock_cls, _, mock_messages = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            await ClaudeProvider().complete("s", "u", 64)
        call_kwargs = mock_messages.create.call_args.kwargs
        assert "```" in call_kwargs["stop_sequences"]

    @pytest.mark.asyncio
    async def test_client_initialised_with_api_key_from_settings(self):
        mock_cls, _, _ = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "sk-ant-secret"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            await ClaudeProvider().complete("s", "u", 64)
        init_kwargs = mock_cls.call_args.kwargs
        assert init_kwargs["api_key"] == "sk-ant-secret"

    @pytest.mark.asyncio
    async def test_client_initialised_with_30s_timeout(self):
        mock_cls, _, _ = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            await ClaudeProvider().complete("s", "u", 64)
        init_kwargs = mock_cls.call_args.kwargs
        assert init_kwargs["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_sdk_exception_propagates(self):
        mock_cls, _, mock_messages = self._make_mock_anthropic("{}")
        mock_messages.create = AsyncMock(side_effect=Exception("Anthropic API error"))
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            with pytest.raises(Exception, match="Anthropic API error"):
                await ClaudeProvider().complete("s", "u", 64)

    @pytest.mark.asyncio
    async def test_client_singleton_reused_across_calls(self):
        """_get_client() must not create a new AsyncAnthropic on every call."""
        mock_cls, _, mock_messages = self._make_mock_anthropic("{}")
        with patch("app.ai.providers.claude.AsyncAnthropic", mock_cls), \
                patch("app.ai.providers.claude.settings") as s:
            s.ANTHROPIC_API_KEY = "test-key"
            s.CLAUDE_MODEL = "claude-sonnet-4-6"
            provider = ClaudeProvider()
            await provider.complete("s", "u", 64)
            await provider.complete("s", "u", 64)
        assert mock_cls.call_count == 1

    def test_provider_name_is_claude(self):
        assert ClaudeProvider().name == "claude"

    def test_is_ai_provider_subclass(self):
        from app.ai.base import AIProvider
        assert issubclass(ClaudeProvider, AIProvider)
