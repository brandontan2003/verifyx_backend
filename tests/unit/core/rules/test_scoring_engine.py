"""
Unit tests for app.core.rules.scoring_engine

All calculate_xp methods are now async — tests use @pytest.mark.asyncio.
KIE happy-path patches httpx.AsyncClient (replacing the old requests.post mock).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.core.rules.scoring_engine as scoring_module
from app.core.rules.scoring_engine import DefaultScoringEngine, KIEScoringEngine, get_scoring_engine


def _make_kie_result_list(xp_value: int) -> list:
    """
    RulesEngine.execute() now returns evaluate_rules_response()'s output directly —
    a list of DMNDecisionResultInfo objects. Build a minimal mock of that shape.
    """
    info = MagicMock()
    info.decision_name = "CalculateXP"
    info.status = "SUCCEEDED"
    info.result = xp_value
    return [info]


class TestDefaultScoringEngine:
    engine = DefaultScoringEngine()

    @pytest.mark.asyncio
    async def test_diff1_fast_band(self):
        # base=10, 5/60=8% < 25% → 2.0x → 20
        assert await self.engine.calculate_xp(1, 5, 60) == 20

    @pytest.mark.asyncio
    async def test_diff2_fast_band(self):
        assert await self.engine.calculate_xp(2, 5, 60) == 40

    @pytest.mark.asyncio
    async def test_diff3_mid_band(self):
        # base=35, 20/60=33% → 1.5x → round(52.5)=52
        assert await self.engine.calculate_xp(3, 20, 60) == round(35 * 1.5)

    @pytest.mark.asyncio
    async def test_diff4_slow_band(self):
        assert await self.engine.calculate_xp(4, 55, 60) == 50

    @pytest.mark.asyncio
    async def test_diff5_fast_band(self):
        assert await self.engine.calculate_xp(5, 5, 60) == 150

    @pytest.mark.asyncio
    async def test_unknown_difficulty_defaults_to_10(self):
        assert await self.engine.calculate_xp(99, 55, 60) == 10

    @pytest.mark.asyncio
    async def test_returns_int(self):
        result = await self.engine.calculate_xp(3, 20, 60)
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_zero_time_limit_returns_base_xp(self):
        assert await self.engine.calculate_xp(1, 0, 0) == 10

    @pytest.mark.asyncio
    async def test_xp_table_parse_failure_uses_hardcoded_defaults(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.XP_TABLE = "THIS IS NOT VALID PYTHON"
            result = await DefaultScoringEngine().calculate_xp(1, 5, 60)
            assert result == 20  # base=10, 2.0x

    @pytest.mark.asyncio
    async def test_all_difficulty_levels_produce_positive_xp(self):
        for diff in range(1, 6):
            assert await self.engine.calculate_xp(diff, 30, 60) > 0


class TestKIEScoringEngine:

    @pytest.mark.asyncio
    async def test_kie_happy_path_returns_server_value(self):
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.RulesEngine.execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = _make_kie_result_list(42)
            result = await engine.calculate_xp(difficulty=2, time_taken=10, time_limit=60)
        assert result == 42

    @pytest.mark.asyncio
    async def test_kie_failure_falls_back_to_default(self):
        from app.core.exceptions.exceptions import RulesException
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.RulesEngine.execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = RulesException()
            # difficulty=1, time_taken=5 → DefaultScoringEngine → 20
            result = await engine.calculate_xp(difficulty=1, time_taken=5, time_limit=60)
        assert result == 20

    @pytest.mark.asyncio
    async def test_kie_fallback_returns_int(self):
        from app.core.exceptions.exceptions import RulesException
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.RulesEngine.execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = RulesException()
            result = await engine.calculate_xp(difficulty=3, time_taken=20, time_limit=60)
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_kie_http_error_falls_back_to_default(self):
        """Non-200 from KIE server raises RulesException → fallback must engage."""
        from app.core.exceptions.exceptions import RulesException
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.RulesEngine.execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = RulesException()
            result = await engine.calculate_xp(difficulty=2, time_taken=30, time_limit=60)
        # base=20, 30/60=50% → 1.2x band → round(20*1.2)=24
        assert result == round(20 * 1.2)


class TestGetScoringEngine:

    def setup_method(self):
        scoring_module._engine = None

    def teardown_method(self):
        scoring_module._engine = None

    def test_default_when_env_absent(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.SCORING_ENGINE = "default"
            mock_settings.XP_TABLE = "{1: 10, 2: 20, 3: 35, 4: 50, 5: 75}"
            engine = get_scoring_engine()
        assert isinstance(engine, DefaultScoringEngine)

    def test_default_when_env_empty(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.SCORING_ENGINE = ""
            mock_settings.XP_TABLE = "{1: 10, 2: 20, 3: 35, 4: 50, 5: 75}"
            engine = get_scoring_engine()
        assert isinstance(engine, DefaultScoringEngine)

    def test_kie_when_env_set(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.SCORING_ENGINE = "kie"
            engine = get_scoring_engine()
        assert isinstance(engine, KIEScoringEngine)

    def test_singleton_returns_same_instance(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.SCORING_ENGINE = "default"
            mock_settings.XP_TABLE = "{1: 10, 2: 20, 3: 35, 4: 50, 5: 75}"
            e1 = get_scoring_engine()
            e2 = get_scoring_engine()
        assert e1 is e2

    def test_unknown_value_falls_back_to_default(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.SCORING_ENGINE = "notarealengine"
            mock_settings.XP_TABLE = "{1: 10, 2: 20, 3: 35, 4: 50, 5: 75}"
            engine = get_scoring_engine()
        assert isinstance(engine, DefaultScoringEngine)
