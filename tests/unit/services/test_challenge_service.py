from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import ChallengeNotFoundException, InvalidAnswerFormatException
from app.core.rules.rules_config import DecisionNameEnum
from app.dto.challenge import GenerateChallengeRequest, SubmitAnswerRequest
from app.services.challenge_service import (
    valid_options_for,
    generate_challenge,
    get_challenge,
    get_challenge_history,
    submit_answer,
)

DB = AsyncMock()

MOCK_SCENARIO = {
    "title": "Test Scenario",
    "content": "A viral claim circulates online.",
    "question": "Is this misinformation?",
    "question_type": "true_false",
    "options": [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}],
    "correct_option_id": "A",
    "difficulty": 2,
    "theme": "misinformation",
    "tags": ["health", "viral"],
}

MOCK_EVALUATION = {
    "is_correct": True,
    "confidence_score": 0.95,
    "reasoning": "Correct — the claim is unsupported.",
}

MOCK_DEBRIEF = {
    "summary": "The article made an unsupported claim.",
    "key_lesson": "Always verify before sharing.",
    "red_flags": ["vague language", "no source"],
    "tip": "Search for the original study.",
}


def _make_challenge(question_type="true_false", correct_option_id="A", room_id=None, status="pending", difficulty=2, ):
    c = MagicMock()
    c.challenge_id = "ch-001"
    c.user_id = "uid-001"
    c.room_id = room_id
    c.theme = "misinformation"
    c.difficulty = difficulty
    c.question_type = question_type
    c.title = "Test Scenario"
    c.content = "A viral claim circulates online."
    c.question = "Is this misinformation?"
    c.options = [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}]
    c.correct_option_id = correct_option_id
    c.tags = ["health"]
    c.status = status
    c.created_at = datetime.now()
    return c


def _make_attempt(attempt_number=1, is_correct=True, xp_earned=20):
    a = MagicMock()
    a.attempt_id = f"att-{attempt_number:03}"
    a.attempt_number = attempt_number
    a.is_correct = is_correct
    a.user_answer = "A"
    a.xp_earned = xp_earned
    a.time_taken_seconds = 10
    a.submitted_at = datetime.now()
    return a


def _make_user(xp=100, streak=3):
    u = MagicMock()
    u.user_id = "uid-001"
    u.xp = xp
    u.streak = streak
    u.last_activity_date = date.today() - timedelta(days=1)
    return u


def _make_challenge_repo(challenge=None, recent_tags=None, completed_count=0, attempt_count=0, has_correct=False,
                         history_rows=None, history_total=0):
    repo = AsyncMock()
    repo.get_challenge_for_user.return_value = challenge or _make_challenge()
    repo.get_recent_tags.return_value = recent_tags or []
    repo.count_completed_challenges.return_value = completed_count
    repo.count_attempts.return_value = attempt_count
    repo.has_correct_attempt.return_value = has_correct
    repo.create_challenge.return_value = challenge or _make_challenge()
    repo.create_attempt.return_value = _make_attempt(attempt_number=attempt_count + 1)
    repo.mark_completed.return_value = None
    repo.get_user_history.return_value = (history_rows or [], history_total)
    return repo


class TestValidOptionsFor:
    def test_mcq_accepts_all_four(self):
        assert valid_options_for("mcq") == ("A", "B", "C", "D")

    def test_true_false_accepts_only_a_and_b(self):
        assert valid_options_for("true_false") == ("A", "B")

    def test_true_false_excludes_c_and_d(self):
        valid = valid_options_for("true_false")
        assert "C" not in valid
        assert "D" not in valid


class TestGenerateChallenge:
    async def test_returns_challenge_response_on_success(self):
        repo = _make_challenge_repo()
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.ai.generate_scenario", AsyncMock(return_value=MOCK_SCENARIO)):
            result = await generate_challenge("uid-001", GenerateChallengeRequest(theme="misinformation"), DB)

        assert result.challenge_id == "ch-001"
        assert result.theme == "misinformation"

    async def test_correct_option_id_not_in_response(self):
        """The correct answer must never be returned to the client at generation time."""
        repo = _make_challenge_repo()
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.ai.generate_scenario", AsyncMock(return_value=MOCK_SCENARIO)):
            result = await generate_challenge("uid-001", GenerateChallengeRequest(theme="misinformation"), DB)

        result_dict = result.model_dump()
        assert "correct_option_id" not in result_dict

    async def test_passes_user_history_and_attempt_count_to_ai(self):
        repo = _make_challenge_repo(recent_tags=["health", "viral"], completed_count=7)
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.ai.generate_scenario",
                      AsyncMock(return_value=MOCK_SCENARIO)) as mock_gen:
            await generate_challenge("uid-001", GenerateChallengeRequest(theme="phishing"), DB)

        mock_gen.assert_called_once_with(
            theme="phishing",
            user_history=["health", "viral"],
            attempt_count=7,
        )

    async def test_persists_challenge_to_db(self):
        repo = _make_challenge_repo()
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.ai.generate_scenario", AsyncMock(return_value=MOCK_SCENARIO)):
            await generate_challenge("uid-001", GenerateChallengeRequest(theme="misinformation"), DB)

        repo.create_challenge.assert_called_once()


class TestGetChallenge:
    async def test_returns_challenge_for_owner(self):
        repo = _make_challenge_repo()
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            result = await get_challenge("uid-001", "ch-001", DB)

        assert result.challenge_id == "ch-001"

    async def test_raises_not_found_when_challenge_missing(self):
        repo = _make_challenge_repo(challenge=None)
        repo.get_challenge_for_user.return_value = None
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            with pytest.raises(ChallengeNotFoundException):
                await get_challenge("uid-001", "ch-missing", DB)

    async def test_correct_option_id_not_in_response(self):
        repo = _make_challenge_repo()
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            result = await get_challenge("uid-001", "ch-001", DB)

        assert "correct_option_id" not in result.model_dump()


class TestGetChallengeHistory:
    async def test_returns_empty_when_no_challenges(self):
        repo = _make_challenge_repo(history_rows=[], history_total=0)
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            result = await get_challenge_history("uid-001", page=1, page_size=20, database=DB)

        assert result.total == 0
        assert result.items == []
        assert result.total_pages == 0

    async def test_maps_challenges_and_attempts_correctly(self):
        challenge = _make_challenge()
        attempts = [_make_attempt(1, True, 40), _make_attempt(2, False, 0)]
        repo = _make_challenge_repo(history_rows=[(challenge, attempts)], history_total=1)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            result = await get_challenge_history("uid-001", page=1, page_size=20, database=DB)

        assert result.total == 1
        assert len(result.items) == 1
        assert len(result.items[0].attempts) == 2
        assert result.items[0].attempts[0].attempt_number == 1
        assert result.items[0].attempts[1].attempt_number == 2

    async def test_challenge_with_no_attempts_returns_empty_list(self):
        challenge = _make_challenge()
        repo = _make_challenge_repo(history_rows=[(challenge, [])], history_total=1)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            result = await get_challenge_history("uid-001", page=1, page_size=20, database=DB)

        assert result.items[0].attempts == []

    async def test_total_pages_calculated_correctly(self):
        rows = [(_make_challenge(), []) for _ in range(3)]
        repo = _make_challenge_repo(history_rows=rows, history_total=25)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            result = await get_challenge_history("uid-001", page=1, page_size=10, database=DB)

        assert result.total_pages == 3  # ceil(25/10)

    async def test_page_and_page_size_passed_to_repo(self):
        repo = _make_challenge_repo()
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            await get_challenge_history("uid-001", page=3, page_size=5, database=DB)

        repo.get_user_history.assert_called_once_with("uid-001", 3, 5)


class TestSubmitAnswer:
    def _payload(self, answer="A", time_taken=10, time_limit=60):
        return SubmitAnswerRequest(
            user_answer=answer,
            time_taken_seconds=time_taken,
            time_limit_seconds=time_limit,
        )

    async def test_raises_not_found_when_challenge_missing(self):
        repo = _make_challenge_repo()
        repo.get_challenge_for_user.return_value = None
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            with pytest.raises(ChallengeNotFoundException):
                await submit_answer("uid-001", "ch-missing", self._payload(), DB)

    async def test_raises_invalid_format_for_c_on_true_false(self):
        repo = _make_challenge_repo(challenge=_make_challenge(question_type="true_false"))
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            with pytest.raises(InvalidAnswerFormatException):
                await submit_answer("uid-001", "ch-001", self._payload(answer="C"), DB)

    async def test_raises_invalid_format_for_d_on_true_false(self):
        repo = _make_challenge_repo(challenge=_make_challenge(question_type="true_false"))
        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo):
            with pytest.raises(InvalidAnswerFormatException):
                await submit_answer("uid-001", "ch-001", self._payload(answer="D"), DB)

    async def test_mcq_accepts_all_four_options(self):
        for answer in ("A", "B", "C", "D"):
            challenge = _make_challenge(
                question_type="mcq",
                correct_option_id=answer,
            )
            challenge.options = [
                {"id": "A", "text": "A"}, {"id": "B", "text": "B"},
                {"id": "C", "text": "C"}, {"id": "D", "text": "D"},
            ]
            repo = _make_challenge_repo(challenge=challenge)
            user = _make_user()

            with (patch("app.services.challenge_service.ChallengeRepository", return_value=repo),
                  patch("app.services.progress_service.UserRepository") as MockUR_PS,
                  patch("app.services.challenge_service.UserRepository") as MockUR_CS,
                  patch("app.services.progress_service.ProgressRepository") as MockPR,
                  patch("app.services.challenge_service.ai.evaluate_response", AsyncMock(return_value=MOCK_EVALUATION)),
                  patch("app.services.challenge_service.ai.generate_debrief",
                        AsyncMock(return_value=MOCK_DEBRIEF)),
                  patch("app.services.progress_service.update_progress", return_value=[
                      MagicMock(decision_name=DecisionNameEnum.CALCULATE_XP, status="SUCCEEDED", result=40)])):
                MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
                MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=user)

                MockPR.return_value.update_progress = AsyncMock(return_value=user)
                MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
                MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])
                # Should not raise
                await submit_answer("uid-001", "ch-001", self._payload(answer=answer), DB)

    async def test_xp_awarded_on_first_correct_attempt(self):
        repo = _make_challenge_repo(attempt_count=0, has_correct=False)
        user = _make_user(xp=0)
        updated_user = _make_user(xp=40, streak=4)

        with (patch("app.services.challenge_service.ChallengeRepository", return_value=repo),
              patch("app.services.progress_service.UserRepository") as MockUR_PS,
              patch("app.services.challenge_service.UserRepository") as MockUR_CS,
              patch("app.services.progress_service.ProgressRepository") as MockPR,
              patch("app.services.challenge_service.ai.evaluate_response",
                    AsyncMock(return_value=MOCK_EVALUATION)),
              patch("app.services.challenge_service.ai.generate_debrief",
                    AsyncMock(return_value=MOCK_DEBRIEF)),
              patch("app.services.progress_service.update_progress",
                    return_value=[
                        MagicMock(decision_name=DecisionNameEnum.CALCULATE_XP, status="SUCCEEDED", result=40)]),
              patch("app.services.challenge_service._check_daily_limit", return_value=None),
              patch("app.services.challenge_service._increment_daily_limit", return_value=None)):
            MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=updated_user)

            MockPR.return_value.update_progress = AsyncMock(return_value=updated_user)
            MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
            MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])

            # difficulty=2, time_taken=5s (fast) → 20 base * 2.0 = 40 XP
            result = await submit_answer(
                "uid-001", "ch-001", self._payload(time_taken=5), DB
            )

        assert result.xp_earned == 40
        assert result.total_xp == 40

    async def test_zero_xp_on_subsequent_correct_attempt(self):
        """Second correct attempt must award 0 XP."""
        repo = _make_challenge_repo(attempt_count=1, has_correct=True)
        user = _make_user(xp=40)

        with (patch("app.services.challenge_service.ChallengeRepository", return_value=repo),
              patch("app.services.challenge_service.UserRepository") as MockUR,
              patch("app.services.challenge_service.update_progress"),
              patch("app.services.challenge_service.ai.evaluate_response",
                    AsyncMock(return_value=MOCK_EVALUATION)),
              patch("app.services.challenge_service.ai.generate_debrief", AsyncMock(return_value=MOCK_DEBRIEF))):
            MockUR.return_value.get_by_user_id = AsyncMock(return_value=user)
            result = await submit_answer("uid-001", "ch-001", self._payload(), DB)

        assert result.xp_earned == 0

    async def test_zero_xp_on_wrong_answer(self):
        wrong_eval = {**MOCK_EVALUATION, "is_correct": False}
        repo = _make_challenge_repo(attempt_count=0, has_correct=False)
        user = _make_user(xp=0)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.UserRepository") as MockUR, \
                patch("app.services.challenge_service.update_progress"), \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=wrong_eval)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)):
            MockUR.return_value.get_by_user_id = AsyncMock(return_value=user)
            result = await submit_answer("uid-001", "ch-001", self._payload(answer="B"), DB)

        assert result.xp_earned == 0

    async def test_attempt_number_increments_correctly(self):
        repo = _make_challenge_repo(attempt_count=3)
        repo.create_attempt.return_value = _make_attempt(attempt_number=4)
        user = _make_user()
        updated_user = _make_user(xp=40)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.progress_service.UserRepository") as MockUR_PS, \
                patch("app.services.challenge_service.UserRepository") as MockUR_CS, \
                patch("app.services.progress_service.ProgressRepository") as MockPR, \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=MOCK_EVALUATION)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)), patch("app.services.progress_service.update_progress",
                                                                   return_value=[MagicMock(
                                                                       decision_name=DecisionNameEnum.CALCULATE_XP,
                                                                       status="SUCCEEDED", result=40)]):
            MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=user)

            MockPR.return_value.update_progress = AsyncMock(return_value=updated_user)
            MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
            MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])
            result = await submit_answer("uid-001", "ch-001", self._payload(), DB)

        assert result.attempt_number == 4

    async def test_correct_option_id_revealed_after_submission(self):
        repo = _make_challenge_repo(challenge=_make_challenge(correct_option_id="A"))
        user = _make_user()
        updated_user = _make_user(xp=40)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.progress_service.UserRepository") as MockUR_PS, \
                patch("app.services.challenge_service.UserRepository") as MockUR_CS, \
                patch("app.services.progress_service.ProgressRepository") as MockPR, \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=MOCK_EVALUATION)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)), patch("app.services.progress_service.update_progress",
                                                                   return_value=[MagicMock(
                                                                       decision_name=DecisionNameEnum.CALCULATE_XP,
                                                                       status="SUCCEEDED", result=40)]):
            MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockPR.return_value.update_progress = AsyncMock(return_value=updated_user)
            MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
            MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])
            result = await submit_answer("uid-001", "ch-001", self._payload(), DB)

        assert "A" in result.correct_answer_display

    async def test_mark_completed_called_on_first_correct(self):
        repo = _make_challenge_repo(has_correct=False)
        user = _make_user()
        updated_user = _make_user(xp=40)

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.progress_service.UserRepository") as MockUR_PS, \
                patch("app.services.challenge_service.UserRepository") as MockUR_CS, \
                patch("app.services.progress_service.ProgressRepository") as MockPR, \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=MOCK_EVALUATION)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)), patch("app.services.progress_service.update_progress",
                                                                   return_value=[MagicMock(
                                                                       decision_name=DecisionNameEnum.CALCULATE_XP,
                                                                       status="SUCCEEDED", result=40)]):
            MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockPR.return_value.update_progress = AsyncMock(return_value=updated_user)
            MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
            MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])
            await submit_answer("uid-001", "ch-001", self._payload(), DB)

        repo.mark_completed.assert_called_once_with("ch-001")

    async def test_mark_completed_not_called_on_subsequent_correct(self):
        repo = _make_challenge_repo(has_correct=True)
        user = _make_user()

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.UserRepository") as MockUR, \
                patch("app.services.challenge_service.update_progress"), \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=MOCK_EVALUATION)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)):
            MockUR.return_value.get_by_user_id = AsyncMock(return_value=user)
            await submit_answer("uid-001", "ch-001", self._payload(), DB)

        repo.mark_completed.assert_not_called()

    async def test_mark_completed_not_called_on_wrong_answer(self):
        wrong_eval = {**MOCK_EVALUATION, "is_correct": False}
        repo = _make_challenge_repo(has_correct=False)
        user = _make_user()

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.UserRepository") as MockUR, \
                patch("app.services.challenge_service.update_progress"), \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=wrong_eval)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)):
            MockUR.return_value.get_by_user_id = AsyncMock(return_value=user)
            await submit_answer("uid-001", "ch-001", self._payload(answer="B"), DB)

        repo.mark_completed.assert_not_called()

    async def test_room_hook_called_when_room_id_present(self):
        challenge = _make_challenge(room_id="room-001")
        repo = _make_challenge_repo(challenge=challenge, has_correct=False)
        user = _make_user()
        updated_user = _make_user(xp=40)

        with (patch("app.services.challenge_service.ChallengeRepository", return_value=repo),
              patch("app.services.progress_service.UserRepository") as MockUR_PS,
              patch("app.services.challenge_service.UserRepository") as MockUR_CS,
              patch("app.services.progress_service.ProgressRepository") as MockPR,
              patch("app.services.challenge_service.ai.evaluate_response",
                    AsyncMock(return_value=MOCK_EVALUATION)),
              patch("app.services.challenge_service.ai.generate_debrief",
                    AsyncMock(return_value=MOCK_DEBRIEF)),
              patch("app.services.room_service.record_room_result", AsyncMock()) as mock_room,
              patch("app.services.progress_service.update_progress",
                    return_value=[
                        MagicMock(decision_name=DecisionNameEnum.CALCULATE_XP, status="SUCCEEDED", result=40)])):
            MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockPR.return_value.update_progress = AsyncMock(return_value=updated_user)
            MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
            MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])
            await submit_answer("uid-001", "ch-001", self._payload(), DB)

        mock_room.assert_called_once()
        call_kwargs = mock_room.call_args.kwargs
        assert call_kwargs["room_id"] == "room-001"
        assert call_kwargs["user_id"] == "uid-001"

    async def test_room_hook_not_called_for_solo_challenge(self):
        challenge = _make_challenge(room_id=None)
        repo = _make_challenge_repo(challenge=challenge, has_correct=False)
        user = _make_user()
        updated_user = _make_user(xp=40)

        with (patch("app.services.challenge_service.ChallengeRepository", return_value=repo),
              patch("app.services.challenge_service.UserRepository") as MockUR_CS,
              patch("app.services.progress_service.UserRepository") as MockUR_PS,
              patch("app.services.progress_service.ProgressRepository") as MockPR,
              patch("app.services.challenge_service.ai.evaluate_response", AsyncMock(return_value=MOCK_EVALUATION)),
              patch("app.services.challenge_service.ai.generate_debrief", AsyncMock(return_value=MOCK_DEBRIEF)),
              patch("app.services.room_service.record_room_result", AsyncMock()) as mock_room,
              patch("app.services.progress_service.update_progress", return_value=[
                  MagicMock(decision_name=DecisionNameEnum.CALCULATE_XP, status="SUCCEEDED", result=40)])):
            MockUR_CS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockUR_PS.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockPR.return_value.update_progress = AsyncMock(return_value=updated_user)
            MockPR.return_value.get_all_badges = AsyncMock(return_value=[])
            MockPR.return_value.get_earned_badge_ids = AsyncMock(return_value=[])
            await submit_answer("uid-001", "ch-001", self._payload(), DB)

        mock_room.assert_not_called()

    async def test_progress_update_not_called_when_xp_is_zero(self):
        """No DB write to progress table when no XP to award."""
        repo = _make_challenge_repo(has_correct=True)  # already correct → xp=0
        user = _make_user()

        with patch("app.services.challenge_service.ChallengeRepository", return_value=repo), \
                patch("app.services.challenge_service.UserRepository") as MockUR, \
                patch("app.services.challenge_service.update_progress") as MockPS, \
                patch("app.services.challenge_service.ai.evaluate_response",
                      AsyncMock(return_value=MOCK_EVALUATION)), \
                patch("app.services.challenge_service.ai.generate_debrief",
                      AsyncMock(return_value=MOCK_DEBRIEF)):
            MockUR.return_value.get_by_user_id = AsyncMock(return_value=user)
            await submit_answer("uid-001", "ch-001", self._payload(), DB)

        MockPS.return_value.update_progress.assert_not_called()
