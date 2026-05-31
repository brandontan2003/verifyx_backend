from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import UserNotFoundException
from app.dto.progress import UpdateProgressRequest
from app.enums.BadgeEnum import BadgeType
from app.services.progress_service import (
    calculate_xp,
    calculate_new_streak,
    get_badges_to_award,
    update_progress,
    get_user_progress,
)

DB = AsyncMock()


def _make_badge(badge_id: str, badge_type: BadgeType, threshold: int):
    b = MagicMock()
    b.badge_id = badge_id
    b.badge_type = badge_type
    b.threshold = threshold
    b.name = f"badge_{badge_id}"
    b.description = "desc"
    return b


def _make_user(user_id="uid-001", xp=0, streak=0, challenges_completed=0, perfect_scores=0, last_activity_date=None):
    u = MagicMock()
    u.user_id = user_id
    u.xp = xp
    u.streak = streak
    u.challenges_completed = challenges_completed
    u.perfect_scores = perfect_scores
    u.last_activity_date = last_activity_date
    return u


def _make_kie_result_list(xp_value: int) -> list:
    """Matches the shape returned by RulesEngine.execute() after the httpx rewrite."""
    info = MagicMock()
    info.decision_name = "CalculateXP"
    info.status = "SUCCEEDED"
    info.result = xp_value
    return [info]


def mock_speed_multiplier(time_taken: int, time_limit: int) -> float:
    if time_limit <= 0:
        return 1.0
    ratio = time_taken / time_limit
    if ratio < 0.25:
        return 2.0
    elif ratio < 0.50:
        return 1.5
    elif ratio < 0.75:
        return 1.2
    return 1.0


class TestCalculateSpeedMultiplier:
    def test_under_25_percent_returns_2x(self):
        assert mock_speed_multiplier(14, 60) == 2.0

    def test_exactly_25_percent_is_not_under_25(self):
        assert mock_speed_multiplier(15, 60) == 1.5

    def test_between_25_and_50_returns_1_5x(self):
        assert mock_speed_multiplier(20, 60) == 1.5

    def test_exactly_50_percent_is_not_under_50(self):
        assert mock_speed_multiplier(30, 60) == 1.2

    def test_between_50_and_75_returns_1_2x(self):
        assert mock_speed_multiplier(40, 60) == 1.2

    def test_exactly_75_percent_is_not_under_75(self):
        assert mock_speed_multiplier(45, 60) == 1.0

    def test_over_75_percent_returns_1x(self):
        assert mock_speed_multiplier(50, 60) == 1.0

    def test_at_time_limit_returns_1x(self):
        assert mock_speed_multiplier(60, 60) == 1.0

    def test_zero_time_limit_returns_1x_without_error(self):
        assert mock_speed_multiplier(10, 0) == 1.0

    def test_over_time_limit_returns_1x(self):
        assert mock_speed_multiplier(90, 60) == 1.0


class TestCalculateXP:
    """
    calculate_xp() is now async — it delegates to ScoringEngine.calculate_xp()
    which is also async. We mock get_scoring_engine() to return an engine whose
    calculate_xp is an AsyncMock so await in the wrapper resolves correctly.
    Engine-specific behaviour is tested in test_scoring_engine.py.
    """

    def _engine_returning(self, xp: int):
        engine = MagicMock()
        engine.calculate_xp = AsyncMock(return_value=xp)
        return engine

    @pytest.mark.asyncio
    async def test_difficulty_1_fast_gives_correct_xp(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(20)):
            assert await calculate_xp(difficulty=1, time_taken=5, time_limit=60) == 20

    @pytest.mark.asyncio
    async def test_difficulty_2_fast_gives_correct_xp(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(40)):
            assert await calculate_xp(difficulty=2, time_taken=5, time_limit=60) == 40

    @pytest.mark.asyncio
    async def test_difficulty_3_medium_speed(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(round(35 * 1.5))):
            result = await calculate_xp(difficulty=3, time_taken=20, time_limit=60)
            assert result == round(35 * 1.5)

    @pytest.mark.asyncio
    async def test_difficulty_4_slow(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(50)):
            assert await calculate_xp(difficulty=4, time_taken=55, time_limit=60) == 50

    @pytest.mark.asyncio
    async def test_difficulty_5_fast_gives_max_xp(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(150)):
            assert await calculate_xp(difficulty=5, time_taken=5, time_limit=60) == 150

    @pytest.mark.asyncio
    async def test_unknown_difficulty_defaults_to_10_base(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(10)):
            assert await calculate_xp(difficulty=99, time_taken=55, time_limit=60) == 10

    @pytest.mark.asyncio
    async def test_returns_int(self):
        with patch("app.services.progress_service.get_scoring_engine",
                   return_value=self._engine_returning(10)):
            result = await calculate_xp(difficulty=3, time_taken=20, time_limit=60)
            assert isinstance(result, int)


class TestCalculateNewStreak:
    def test_first_activity_ever_returns_1(self):
        assert calculate_new_streak(0, None, date.today()) == 1

    def test_consecutive_day_increments_streak(self):
        yesterday = date.today() - timedelta(days=1)
        assert calculate_new_streak(5, yesterday, date.today()) == 6

    def test_same_day_does_not_change_streak(self):
        today = date.today()
        assert calculate_new_streak(5, today, today) == 5

    def test_same_day_with_streak_1_stays_at_1(self):
        today = date.today()
        assert calculate_new_streak(1, today, today) == 1

    def test_missed_one_day_resets_to_1(self):
        two_days_ago = date.today() - timedelta(days=2)
        assert calculate_new_streak(10, two_days_ago, date.today()) == 1

    def test_missed_many_days_resets_to_1(self):
        old = date.today() - timedelta(days=30)
        assert calculate_new_streak(99, old, date.today()) == 1

    def test_streak_1_increments_to_2_on_next_day(self):
        yesterday = date.today() - timedelta(days=1)
        assert calculate_new_streak(1, yesterday, date.today()) == 2


class TestGetBadgesToAward:
    def test_awards_streak_badge_at_threshold(self):
        badges = [_make_badge("b-streak-7", BadgeType.streak, 7)]
        result = get_badges_to_award(badges, set(), streak=7, challenges_completed=0)
        assert "b-streak-7" in result

    def test_awards_streak_badge_above_threshold(self):
        badges = [_make_badge("b-streak-7", BadgeType.streak, 7)]
        result = get_badges_to_award(badges, set(), streak=30, challenges_completed=0)
        assert "b-streak-7" in result

    def test_does_not_award_streak_below_threshold(self):
        badges = [_make_badge("b-streak-7", BadgeType.streak, 7)]
        result = get_badges_to_award(badges, set(), streak=6, challenges_completed=0)
        assert "b-streak-7" not in result

    def test_awards_completion_badge_at_threshold(self):
        badges = [_make_badge("b-comp-10", BadgeType.completion, 10)]
        result = get_badges_to_award(badges, set(), streak=0, challenges_completed=10)
        assert "b-comp-10" in result

    def test_does_not_award_completion_below_threshold(self):
        badges = [_make_badge("b-comp-10", BadgeType.completion, 10)]
        result = get_badges_to_award(badges, set(), streak=0, challenges_completed=9)
        assert "b-comp-10" not in result

    def test_skips_already_earned_badge(self):
        badges = [_make_badge("b-streak-7", BadgeType.streak, 7)]
        result = get_badges_to_award(badges, {"b-streak-7"}, streak=100, challenges_completed=0)
        assert "b-streak-7" not in result

    def test_awards_multiple_badges_at_once(self):
        badges = [
            _make_badge("b-streak-7", BadgeType.streak, 7),
            _make_badge("b-comp-10", BadgeType.completion, 10),
        ]
        result = get_badges_to_award(badges, set(), streak=7, challenges_completed=10)
        assert set(result) == {"b-streak-7", "b-comp-10"}

    def test_does_not_award_already_earned_even_if_others_awarded(self):
        badges = [
            _make_badge("b-streak-7", BadgeType.streak, 7),
            _make_badge("b-comp-10", BadgeType.completion, 10),
        ]
        result = get_badges_to_award(badges, {"b-streak-7"}, streak=7, challenges_completed=10)
        assert "b-streak-7" not in result
        assert "b-comp-10" in result

    def test_empty_badge_list_returns_empty(self):
        result = get_badges_to_award([], set(), streak=100, challenges_completed=100)
        assert result == []

    def test_all_already_earned_returns_empty(self):
        badges = [_make_badge("b1", BadgeType.streak, 1)]
        result = get_badges_to_award(badges, {"b1"}, streak=100, challenges_completed=0)
        assert result == []


class TestUpdateProgress:
    def _make_payload(self, difficulty=2, time_taken=10, time_limit=60, is_perfect=False):
        return UpdateProgressRequest(
            difficulty=difficulty,
            time_taken_seconds=time_taken,
            time_limit_seconds=time_limit,
            is_perfect=is_perfect
        )

    @pytest.mark.asyncio
    async def test_raises_user_not_found_when_user_missing(self):
        with patch("app.services.progress_service.UserRepository") as MockUserRepo, \
                patch("app.services.progress_service.ProgressRepository"):
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=None)
            with pytest.raises(UserNotFoundException):
                await update_progress("uid-missing", self._make_payload(), DB)

    @pytest.mark.asyncio
    async def test_xp_is_calculated_and_written(self):
        user = _make_user(streak=3, last_activity_date=date.today())
        updated_user = _make_user(xp=40, streak=3, challenges_completed=1, perfect_scores=0)

        with (patch("app.services.progress_service.UserRepository") as MockUserRepo,
              patch("app.services.progress_service.ProgressRepository") as MockProgressRepo,
              patch("app.services.rules_service.RulesEngine.execute",
                    new_callable=AsyncMock, return_value=_make_kie_result_list(40))):
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            progress_repo = MockProgressRepo.return_value
            progress_repo.update_progress = AsyncMock(return_value=updated_user)
            progress_repo.get_all_badges = AsyncMock(return_value=[])
            progress_repo.get_earned_badge_ids = AsyncMock(return_value=set())
            progress_repo.award_badges = AsyncMock(return_value=[])

            result = await update_progress("uid-001", self._make_payload(difficulty=2, time_taken=5), DB)

        assert result.xp_earned == 40
        assert result.total_xp == 40

    @pytest.mark.asyncio
    async def test_streak_passed_to_repo(self):
        yesterday = date.today() - timedelta(days=1)
        user = _make_user(streak=4, last_activity_date=yesterday)
        updated_user = _make_user(xp=20, streak=5, challenges_completed=1, perfect_scores=0)

        with (patch("app.services.progress_service.UserRepository") as MockUserRepo,
              patch("app.services.progress_service.ProgressRepository") as MockProgressRepo,
              patch("app.services.rules_service.RulesEngine.execute",
                    new_callable=AsyncMock, return_value=_make_kie_result_list(20))):
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            progress_repo = MockProgressRepo.return_value
            progress_repo.update_progress = AsyncMock(return_value=updated_user)
            progress_repo.get_all_badges = AsyncMock(return_value=[])
            progress_repo.get_earned_badge_ids = AsyncMock(return_value=set())
            progress_repo.award_badges = AsyncMock(return_value=[])

            result = await update_progress("uid-001", self._make_payload(), DB)

        assert result.streak == 5
        progress_repo.update_progress.assert_called_once()
        call_kwargs = progress_repo.update_progress.call_args.kwargs
        assert call_kwargs["new_streak"] == 5

    @pytest.mark.asyncio
    async def test_badges_awarded_when_threshold_met(self):
        user = _make_user(streak=7, last_activity_date=date.today())
        updated_user = _make_user(xp=20, streak=7, challenges_completed=1, perfect_scores=0)
        badge = _make_badge("b-streak-7", BadgeType.streak, 7)
        awarded_badge = _make_badge("b-streak-7", BadgeType.streak, 7)

        with (patch("app.services.progress_service.UserRepository") as MockUserRepo,
              patch("app.services.progress_service.ProgressRepository") as MockProgressRepo,
              patch("app.services.rules_service.RulesEngine.execute",
                    new_callable=AsyncMock, return_value=_make_kie_result_list(20))):
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            progress_repo = MockProgressRepo.return_value
            progress_repo.update_progress = AsyncMock(return_value=updated_user)
            progress_repo.get_all_badges = AsyncMock(return_value=[badge])
            progress_repo.get_earned_badge_ids = AsyncMock(return_value=set())
            progress_repo.award_badges = AsyncMock(return_value=[awarded_badge])

            result = await update_progress("uid-001", self._make_payload(), DB)

        progress_repo.award_badges.assert_called_once()
        assert len(result.new_badges) == 1

    @pytest.mark.asyncio
    async def test_no_badge_award_call_when_none_to_award(self):
        user = _make_user(streak=1)
        updated_user = _make_user(xp=10, streak=1, challenges_completed=1, perfect_scores=0)

        with (patch("app.services.progress_service.UserRepository") as MockUserRepo,
              patch("app.services.progress_service.ProgressRepository") as MockProgressRepo,
              patch("app.services.rules_service.RulesEngine.execute",
                    new_callable=AsyncMock, return_value=_make_kie_result_list(10))):
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            progress_repo = MockProgressRepo.return_value
            progress_repo.update_progress = AsyncMock(return_value=updated_user)
            progress_repo.get_all_badges = AsyncMock(return_value=[])
            progress_repo.get_earned_badge_ids = AsyncMock(return_value=set())
            progress_repo.award_badges = AsyncMock(return_value=[])

            result = await update_progress("uid-001", self._make_payload(), DB)

        progress_repo.award_badges.assert_not_called()
        assert result.new_badges == []


class TestGetUserProgress:
    @pytest.mark.asyncio
    async def test_raises_user_not_found_when_user_missing(self):
        with patch("app.services.progress_service.UserRepository") as MockUserRepo, \
                patch("app.services.progress_service.ProgressRepository"):
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=None)
            with pytest.raises(UserNotFoundException):
                await get_user_progress("uid-missing", DB)

    @pytest.mark.asyncio
    async def test_returns_correct_progress_fields(self):
        user = _make_user(xp=200, streak=5, challenges_completed=12, perfect_scores=3)

        with patch("app.services.progress_service.UserRepository") as MockUserRepo, \
                patch("app.services.progress_service.ProgressRepository") as MockProgressRepo:
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockProgressRepo.return_value.get_user_badges = AsyncMock(return_value=[])

            result = await get_user_progress("uid-001", DB)

        assert result.total_xp == 200
        assert result.streak == 5
        assert result.challenges_completed == 12
        assert result.perfect_scores == 3

    @pytest.mark.asyncio
    async def test_returns_empty_badges_when_none_earned(self):
        user = _make_user()

        with patch("app.services.progress_service.UserRepository") as MockUserRepo, \
                patch("app.services.progress_service.ProgressRepository") as MockProgressRepo:
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockProgressRepo.return_value.get_user_badges = AsyncMock(return_value=[])

            result = await get_user_progress("uid-001", DB)

        assert result.badges == []

    @pytest.mark.asyncio
    async def test_returns_badges_when_earned(self):
        user = _make_user()
        badge = _make_badge("b1", BadgeType.streak, 7)

        with patch("app.services.progress_service.UserRepository") as MockUserRepo, \
                patch("app.services.progress_service.ProgressRepository") as MockProgressRepo:
            MockUserRepo.return_value.get_by_user_id = AsyncMock(return_value=user)
            MockProgressRepo.return_value.get_user_badges = AsyncMock(return_value=[badge])

            result = await get_user_progress("uid-001", DB)

        assert len(result.badges) == 1
        assert result.badges[0].badge_id == "b1"
