"""
Unit tests for app.services.verify_service

Covers:
  - AI_PLATFORM_CONTEXT injected into system prompt (no "Singapore" hardcoding)
  - Verdict passthrough, whitelist coercion, confidence clamping
  - Disclaimer selection: insufficient / low-confidence / normal
  - Vague input path (insufficient_information)
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.dto.news import VerifyRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ai_response(verdict="legitimate", confidence=90, red_flags=None, recommendation="All good.",
                      reasoning="Looks fine."):
    import json
    payload = {
        "verdict": verdict,
        "confidence": confidence,
        "red_flags": red_flags or [],
        "recommendation": recommendation,
        "reasoning": reasoning,
    }
    return json.dumps(payload)


async def _call_verify(content: str, platform_context: str = "a test platform", child_safety: bool = False):
    from app.services.verify_service import verify_content
    with patch("app.services.verify_service.settings") as mock_settings:
        mock_settings.AI_PLATFORM_CONTEXT = platform_context
        mock_settings.CHILD_SAFETY_MODE = child_safety
        with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _mock_ai_response()
            result = await verify_content(VerifyRequest(content=content))
            return result, mock_ai


# ---------------------------------------------------------------------------
# Platform context injection
# ---------------------------------------------------------------------------

class TestPlatformContextInjection:

    @pytest.mark.asyncio
    async def test_platform_context_injected_into_system_prompt(self):
        from app.services.verify_service import verify_content
        with patch("app.services.verify_service.settings") as mock_settings:
            mock_settings.AI_PLATFORM_CONTEXT = "a custom platform for testing"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = _mock_ai_response()
                await verify_content(VerifyRequest(content="some content"))
                call_kwargs = mock_ai.call_args
                system_prompt = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert "a custom platform for testing" in system_prompt

    @pytest.mark.asyncio
    async def test_singapore_not_hardcoded_in_system_prompt(self):
        from app.services.verify_service import verify_content
        with patch("app.services.verify_service.settings") as mock_settings:
            mock_settings.AI_PLATFORM_CONTEXT = "a digital literacy platform"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = _mock_ai_response()
                await verify_content(VerifyRequest(content="some content"))
                call_kwargs = mock_ai.call_args
                system_prompt = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert "Singapore" not in system_prompt
                assert "singapore" not in system_prompt

    @pytest.mark.asyncio
    async def test_giggle_academy_context_injected(self):
        """Giggle Academy deployment can swap context without code changes."""
        from app.services.verify_service import verify_content
        giggle_context = "a free, global K-12 digital literacy education platform"
        with patch("app.services.verify_service.settings") as mock_settings:
            mock_settings.AI_PLATFORM_CONTEXT = giggle_context
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = _mock_ai_response()
                await verify_content(VerifyRequest(content="test content"))
                call_kwargs = mock_ai.call_args
                system_prompt = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert giggle_context in system_prompt


# ---------------------------------------------------------------------------
# Verdict and confidence handling
# ---------------------------------------------------------------------------

class TestVerdictHandling:

    @pytest.mark.asyncio
    async def test_valid_verdict_passthrough(self):
        import json
        from app.services.verify_service import verify_content
        for verdict in ["legitimate", "suspicious", "scam", "misinformation", "insufficient_information"]:
            with patch("app.services.verify_service.settings") as s:
                s.AI_PLATFORM_CONTEXT = "test"
                with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                    mock_ai.return_value = json.dumps({"verdict": verdict, "confidence": 80,
                                                       "red_flags": [], "recommendation": "ok",
                                                       "reasoning": "r"})
                    result = await verify_content(VerifyRequest(content="test"))
                    assert result.verdict == verdict

    @pytest.mark.asyncio
    async def test_hallucinated_verdict_coerced_to_insufficient_information(self):
        import json
        from app.services.verify_service import verify_content
        with patch("app.services.verify_service.settings") as s:
            s.AI_PLATFORM_CONTEXT = "test"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"verdict": "DEFINITELY_FAKE", "confidence": 99,
                                                   "red_flags": [], "recommendation": "ok",
                                                   "reasoning": "r"})
                result = await verify_content(VerifyRequest(content="test"))
                assert result.verdict == "insufficient_information"

    @pytest.mark.asyncio
    async def test_confidence_clamped_above_100(self):
        import json
        from app.services.verify_service import verify_content
        with patch("app.services.verify_service.settings") as s:
            s.AI_PLATFORM_CONTEXT = "test"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"verdict": "legitimate", "confidence": 999,
                                                   "red_flags": [], "recommendation": "ok",
                                                   "reasoning": "r"})
                result = await verify_content(VerifyRequest(content="test"))
                assert result.confidence == 100

    @pytest.mark.asyncio
    async def test_confidence_clamped_below_0(self):
        import json
        from app.services.verify_service import verify_content
        with patch("app.services.verify_service.settings") as s:
            s.AI_PLATFORM_CONTEXT = "test"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"verdict": "legitimate", "confidence": -50,
                                                   "red_flags": [], "recommendation": "ok",
                                                   "reasoning": "r"})
                result = await verify_content(VerifyRequest(content="test"))
                assert result.confidence == 0


# ---------------------------------------------------------------------------
# Disclaimer selection
# ---------------------------------------------------------------------------

class TestDisclaimerSelection:

    @pytest.mark.asyncio
    async def test_insufficient_information_gets_paste_disclaimer(self):
        import json
        from app.services.verify_service import verify_content, _DISCLAIMER_INSUFFICIENT
        with patch("app.services.verify_service.settings") as s:
            s.AI_PLATFORM_CONTEXT = "test"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"verdict": "insufficient_information", "confidence": 0,
                                                   "red_flags": [], "recommendation": "paste content",
                                                   "reasoning": "r"})
                result = await verify_content(VerifyRequest(content="?"))
                assert result.disclaimer == _DISCLAIMER_INSUFFICIENT

    @pytest.mark.asyncio
    async def test_low_confidence_gets_warning_disclaimer(self):
        import json
        from app.services.verify_service import verify_content, _DISCLAIMER_LOW
        with patch("app.services.verify_service.settings") as s:
            s.AI_PLATFORM_CONTEXT = "test"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"verdict": "suspicious", "confidence": 50,
                                                   "red_flags": ["vague"], "recommendation": "check",
                                                   "reasoning": "r"})
                result = await verify_content(VerifyRequest(content="some claim"))
                assert result.disclaimer == _DISCLAIMER_LOW
                assert result.is_low_confidence is True

    @pytest.mark.asyncio
    async def test_high_confidence_gets_standard_disclaimer(self):
        import json
        from app.services.verify_service import verify_content, _DISCLAIMER_HIGH
        with patch("app.services.verify_service.settings") as s:
            s.AI_PLATFORM_CONTEXT = "test"
            with patch("app.services.verify_service.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"verdict": "scam", "confidence": 95,
                                                   "red_flags": ["urgency"], "recommendation": "ignore",
                                                   "reasoning": "r"})
                result = await verify_content(VerifyRequest(content="win a prize"))
                assert result.disclaimer == _DISCLAIMER_HIGH
                assert result.is_low_confidence is False
