from anthropic import AsyncAnthropic
from anthropic.types import MessageParam

from app.ai.base import AIProvider
from app.config import settings

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=30.0)
    return _client


class ClaudeProvider(AIProvider):

    @property
    def name(self) -> str:
        return "claude"

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        message = MessageParam(role="user", content=user)
        message = await _get_client().messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[message],
            stop_sequences=["```"]
        )
        return message.content[0].text
