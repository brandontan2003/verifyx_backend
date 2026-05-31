import json
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.client import _parse_json


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


class TestGenerateScenario:

    def _valid_mcq_response(self, correct_option_id="B"):
        import json
        return json.dumps({
            "title": "Suspicious Viral Post",
            "content": "A viral post claims a local hospital is giving away free medication.",
            "question": "Is this post likely legitimate?",
            "question_type": "mcq",
            "options": [
                {"id": "A", "text": "Yes, hospitals do this"},
                {"id": "B", "text": "No, this looks like a scam"},
                {"id": "C", "text": "Cannot tell from the post"},
                {"id": "D", "text": "Only if it has a phone number"},
            ],
            "correct_option_id": correct_option_id,
            "difficulty": 2,
            "theme": "scam",
            "tags": ["health", "viral"],
        })

    def _valid_true_false_response(self, correct_option_id="A"):
        import json
        return json.dumps({
            "title": "Headline Check",
            "content": "A headline reads: Scientists discover cure for all diseases.",
            "question": "This headline contains signs of misinformation.",
            "question_type": "true_false",
            "options": [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}],
            "correct_option_id": correct_option_id,
            "difficulty": 1,
            "theme": "misinformation",
            "tags": ["headline", "health"],
        })

    @pytest.mark.asyncio
    async def test_mcq_response_returned_as_dict(self):
        from app.ai.client import generate_scenario
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = self._valid_mcq_response()
                result = await generate_scenario("scam", [], 5)
        assert isinstance(result, dict)
        assert result["question_type"] == "mcq"

    @pytest.mark.asyncio
    async def test_true_false_options_always_normalised(self):
        """true_false options must always be exactly [A=True, B=False] regardless of AI output."""
        import json
        from app.ai.client import generate_scenario
        response = json.dumps({
            "title": "t", "content": "c", "question": "q",
            "question_type": "true_false",
            # AI returned different text — must be overwritten
            "options": [{"id": "A", "text": "Correct"}, {"id": "B", "text": "Wrong"}],
            "correct_option_id": "A", "difficulty": 1, "theme": "misinformation", "tags": [],
        })
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = response
                result = await generate_scenario("misinformation", [], 0)
        assert result["options"] == [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}]

    @pytest.mark.asyncio
    async def test_invalid_question_type_raises_value_error(self):
        import json
        from app.ai.client import generate_scenario
        bad = json.dumps({
            "title": "t", "content": "c", "question": "q",
            "question_type": "essay",
            "options": [], "correct_option_id": "A",
            "difficulty": 1, "theme": "scam", "tags": [],
        })
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = bad
                with pytest.raises(ValueError, match="invalid question_type"):
                    await generate_scenario("scam", [], 0)

    @pytest.mark.asyncio
    async def test_true_false_wrong_correct_option_raises_value_error(self):
        import json
        from app.ai.client import generate_scenario
        bad = json.dumps({
            "title": "t", "content": "c", "question": "q",
            "question_type": "true_false",
            "options": [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}],
            "correct_option_id": "C",  # invalid for true_false
            "difficulty": 1, "theme": "misinformation", "tags": [],
        })
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = bad
                with pytest.raises(ValueError, match="true_false correct_option_id"):
                    await generate_scenario("misinformation", [], 0)

    @pytest.mark.asyncio
    async def test_mcq_correct_option_not_in_options_raises_value_error(self):
        import json
        from app.ai.client import generate_scenario
        bad = json.dumps({
            "title": "t", "content": "c", "question": "q",
            "question_type": "mcq",
            "options": [
                {"id": "A", "text": "opt1"}, {"id": "B", "text": "opt2"},
                {"id": "C", "text": "opt3"}, {"id": "D", "text": "opt4"},
            ],
            "correct_option_id": "E",  # not in A-D
            "difficulty": 1, "theme": "scam", "tags": [],
        })
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = bad
                with pytest.raises(ValueError, match="correct_option_id"):
                    await generate_scenario("scam", [], 0)

    @pytest.mark.asyncio
    async def test_user_history_truncated_to_last_10_tags(self):
        """Only the 10 most recent history tags must be passed to the prompt."""
        from app.ai.client import generate_scenario
        history = [f"tag{i}" for i in range(20)]  # 20 tags
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = self._valid_mcq_response()
                await generate_scenario("scam", history, 20)
                user_prompt = mock_ai.call_args.kwargs.get("user") or mock_ai.call_args.args[1]
        # Only the last 10 tags should appear
        assert "tag10" in user_prompt
        assert "tag19" in user_prompt
        assert "tag0" not in user_prompt
        assert "tag9" not in user_prompt

    @pytest.mark.asyncio
    async def test_empty_history_sends_none_string(self):
        from app.ai.client import generate_scenario
        with patch("app.ai.client.settings") as s:
            s.CHILD_SAFETY_MODE = False
            with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = self._valid_mcq_response()
                await generate_scenario("phishing", [], 0)
                user_prompt = mock_ai.call_args.kwargs.get("user") or mock_ai.call_args.args[1]
        assert "none" in user_prompt.lower()


class TestEvaluateResponse:

    @pytest.mark.asyncio
    async def test_returns_dict_with_is_correct(self):
        import json
        from app.ai.client import evaluate_response
        with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = json.dumps({
                "is_correct": True, "confidence_score": 1.0, "reasoning": "Correct."
            })
            result = await evaluate_response("content", "question", "mcq", "B", "It is a scam", "B")
        assert result["is_correct"] is True
        assert result["confidence_score"] == 1.0

    @pytest.mark.asyncio
    async def test_correct_option_and_user_answer_in_prompt(self):
        import json
        from app.ai.client import evaluate_response
        with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = json.dumps({
                "is_correct": False, "confidence_score": 0.9, "reasoning": "Wrong."
            })
            await evaluate_response("content", "question", "true_false", "A", "True", "B")
            user_prompt = mock_ai.call_args.kwargs.get("user") or mock_ai.call_args.args[1]
        assert "Option A" in user_prompt
        assert "Option B" in user_prompt
        assert "True" in user_prompt


class TestGenerateDebrief:

    def _debrief_response(self):
        import json
        return json.dumps({
            "summary": "The post used urgency to pressure victims.",
            "key_lesson": "Always verify urgent requests through official channels.",
            "red_flags": ["urgency language", "unsolicited contact", "prize claim"],
            "tip": "Call the organisation directly using a number from their official website.",
        })

    @pytest.mark.asyncio
    async def test_returns_dict_with_required_keys(self):
        from app.ai.client import generate_debrief
        with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = self._debrief_response()
            result = await generate_debrief(
                "content", "question", "mcq", "B", "It is a scam",
                "A", "It is legitimate", False, 2, 45, 60, 3
            )
        assert "summary" in result
        assert "key_lesson" in result
        assert "red_flags" in result
        assert "tip" in result

    @pytest.mark.asyncio
    async def test_correct_and_incorrect_labels_in_prompt(self):
        from app.ai.client import generate_debrief
        with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = self._debrief_response()
            await generate_debrief(
                "c", "q", "true_false", "A", "True",
                "B", "False", False, 1, 55, 60, 1
            )
            user_prompt = mock_ai.call_args.kwargs.get("user") or mock_ai.call_args.args[1]
        assert "Incorrect" in user_prompt

    @pytest.mark.asyncio
    async def test_correct_result_label_in_prompt(self):
        from app.ai.client import generate_debrief
        with patch("app.ai.client.complete_with_fallback", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = self._debrief_response()
            await generate_debrief(
                "c", "q", "mcq", "B", "Scam",
                "B", "Scam", True, 3, 10, 60, 2
            )
            user_prompt = mock_ai.call_args.kwargs.get("user") or mock_ai.call_args.args[1]
        assert "Correct" in user_prompt
