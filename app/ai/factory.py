"""
AI provider factory.

AI_PROVIDER env var controls which provider is primary:
  "claude"  → ClaudeProvider (default)
  "ollama"  → OllamaProvider (local model, no Claude needed)

Fallback:
  If the primary provider is Claude and it raises any exception, the factory
  automatically retries with OllamaProvider. This means Claude downtime does
  not take down the app — users get slightly lower-quality responses instead
  of a 500 error.

  If the primary is already Ollama (AI_PROVIDER=ollama), there is no fallback —
  a failure surfaces as an exception to the caller.
"""
from app.ai.base import AIProvider
from app.ai.providers.claude import ClaudeProvider
from app.ai.providers.groq import GroqProvider
from app.config import settings
from app.core.logger import logger

_primary: AIProvider | None = None
_fallback: AIProvider | None = None


def _init_providers() -> tuple[AIProvider, AIProvider | None]:
    provider = settings.AI_PROVIDER.strip().lower()
    if provider == "groq":
        return GroqProvider(), None
    # Default: Claude primary, Groq fallback
    return ClaudeProvider(), GroqProvider()


def get_primary() -> AIProvider:
    global _primary, _fallback
    if _primary is None:
        _primary, _fallback = _init_providers()
    return _primary


def get_fallback() -> AIProvider | None:
    global _primary, _fallback
    if _primary is None:
        _primary, _fallback = _init_providers()
    return _fallback


async def complete_with_fallback(system: str, user: str, max_tokens: int) -> str:
    """
    Call the primary provider. On any exception, log the failure and
    retry once with the fallback. Raises if both fail.
    """
    primary = get_primary()
    try:
        return await primary.complete(system, user, max_tokens)
    except Exception as primary_exc:
        fallback = get_fallback()
        if fallback is None:
            raise

        logger.warning(
            "AI primary provider '%s' failed (%s: %s) — falling back to '%s'",
            primary.name,
            type(primary_exc).__name__,
            primary_exc,
            fallback.name
        )
        try:
            return await fallback.complete(system, user, max_tokens)
        except Exception as fallback_exc:
            logger.error(
                "AI fallback provider '%s' also failed: %s",
                fallback.name,
                fallback_exc,
                exc_info=True
            )
            raise
