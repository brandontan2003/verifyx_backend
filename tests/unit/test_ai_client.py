"""
Unit tests for app.ai.client

Covers:
  - CHILD_SAFETY_MODE=True appends suffix to scenario generation system prompt
  - CHILD_SAFETY_MODE=False does NOT append suffix
  - evaluate_response and generate_debrief are never modified by child safety mode
  - _parse_json: direct parse, greedy regex, fence strip, ValueError on all failure
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.client import _parse_json


# ---------------------------------------------------------------------------
# Child safety suffix — generate_scenario
# ---------------------------------------------------------------------------

class TestChildSafetyMode:

    def _make_scenario_response(self):
        return json.dumps({
            "title": "Test", "content": "Content.", "question": "Q?",
            "question_type": "true_false",
            "options": [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}],
            "correct_option_id": "A", "difficulty": 1,
            "theme": "misinformation", "tags": ["test"]
        })

    @pytest.mark.asyncio
    async def test_child_safety_suffix_appended_when_mode_true(self):
        from app.ai.client import generate_scenario
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.CHILD_SAFETY_MODE = True
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = self._make_scenario_response()
                await generate_scenario("misinformation", [], 0)
                call_kwargs = mock_ai.call_args
                system = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert "CHILD SAFETY" in system

    @pytest.mark.asyncio
    async def test_child_safety_suffix_not_appended_when_mode_false(self):
        from app.ai.client import generate_scenario
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = self._make_scenario_response()
                await generate_scenario("misinformation", [], 0)
                call_kwargs = mock_ai.call_args
                system = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert "CHILD SAFETY" not in system

    @pytest.mark.asyncio
    async def test_evaluate_response_never_has_child_safety_suffix(self):
        """evaluate_response must never be modified by CHILD_SAFETY_MODE — it has no generation."""
        from app.ai.client import evaluate_response
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.CHILD_SAFETY_MODE = True
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({"is_correct": True, "confidence_score": 1.0, "reasoning": "ok"})
                await evaluate_response("content", "question", "true_false", "A", "True", "A")
                call_kwargs = mock_ai.call_args
                system = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert "CHILD SAFETY" not in system

    @pytest.mark.asyncio
    async def test_generate_debrief_never_has_child_safety_suffix(self):
        from app.ai.client import generate_debrief
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.CHILD_SAFETY_MODE = True
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = json.dumps({
                    "summary": "s", "key_lesson": "k",
                    "red_flags": ["f"], "tip": "t"
                })
                await generate_debrief("content", "q", "true_false", "A", "True", "A", "True",
                                       True, 2, 10, 60, 1)
                call_kwargs = mock_ai.call_args
                system = call_kwargs.kwargs.get("system") or call_kwargs.args[0]
                assert "CHILD SAFETY" not in system


# ---------------------------------------------------------------------------
# _parse_json — three-stage parser
# ---------------------------------------------------------------------------

class TestParseJson:

    def test_direct_json_parse(self):
        data = _parse_json('{"verdict": "scam"}', "test")
        assert data == {"verdict": "scam"}

    def test_prose_wrapped_json_extracted(self):
        raw = 'Here is the response: {"verdict": "scam", "confidence": 90} done.'
        data = _parse_json(raw, "test")
        assert data["verdict"] == "scam"

    def test_markdown_fence_stripped(self):
        raw = '```json\n{"verdict": "legitimate"}\n```'
        data = _parse_json(raw, "test")
        assert data["verdict"] == "legitimate"

    def test_value_error_on_all_stages_failing(self):
        with pytest.raises(ValueError, match="malformed JSON"):
            _parse_json("THIS IS NOT JSON AT ALL", "test")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_json("", "test")

    def test_nested_json_parsed_correctly(self):
        raw = json.dumps({"options": [{"id": "A", "text": "True"}], "difficulty": 2})
        data = _parse_json(raw, "test")
        assert data["difficulty"] == 2
        assert data["options"][0]["id"] == "A"
