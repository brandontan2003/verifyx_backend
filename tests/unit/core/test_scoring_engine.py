from unittest.mock import MagicMock, patch

import app.core.rules.scoring_engine as scoring_module
from app.core.rules.scoring_engine import DefaultScoringEngine, KIEScoringEngine, get_scoring_engine


def _make_kie_response(xp_value: int) -> MagicMock:
    """Minimal mock that satisfies evaluate_result_list()."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "type": "SUCCESS",
        "msg": "Message",
        "result": {
            "dmn-evaluation-result": {
                "messages": [],
                "model-namespace": "model url",
                "model-name": "Xp",
                "decision-name": "CalculateXP",
                "dmn-context": {
                    "InputData": {"difficulty": 1, "time_limit": 60, "time_taken": 5},
                    "CalculateXP": xp_value,
                },
                "decision-results": {
                    "_BE7648BE": {
                        "messages": [],
                        "decision-id": "_BE7648BE",
                        "decision-name": "CalculateXP",
                        "result": xp_value,
                        "status": "SUCCEEDED",
                    }
                },
            }
        },
    }
    return mock_resp


class TestDefaultScoringEngine:
    engine = DefaultScoringEngine()

    # --- speed multiplier bands (via full calculate_xp path) ---

    def test_diff1_fast_band(self):
        # base=10, 5/60=8% < 25% → 2.0x → 20
        assert self.engine.calculate_xp(1, 5, 60) == 20

    def test_diff2_fast_band(self):
        # base=20, 2.0x → 40
        assert self.engine.calculate_xp(2, 5, 60) == 40

    def test_diff3_mid_band(self):
        # base=35, 20/60=33% → 1.5x → round(52.5)=52
        assert self.engine.calculate_xp(3, 20, 60) == round(35 * 1.5)

    def test_diff4_slow_band(self):
        # base=50, 55/60=91% → 1.0x → 50
        assert self.engine.calculate_xp(4, 55, 60) == 50

    def test_diff5_fast_band(self):
        # base=75, 2.0x → 150
        assert self.engine.calculate_xp(5, 5, 60) == 150

    def test_unknown_difficulty_defaults_to_10(self):
        # .get(99, 10) → 10, slow → 1.0x → 10
        assert self.engine.calculate_xp(99, 55, 60) == 10

    def test_returns_int(self):
        result = self.engine.calculate_xp(3, 20, 60)
        assert isinstance(result, int)

    def test_zero_time_limit_returns_base_xp(self):
        # Division-by-zero guard → multiplier=1.0
        assert self.engine.calculate_xp(1, 0, 0) == 10

    def test_xp_table_parse_failure_uses_hardcoded_defaults(self):
        with patch("app.core.rules.scoring_engine.settings") as mock_settings:
            mock_settings.XP_TABLE = "THIS IS NOT VALID PYTHON"
            # Should not raise; falls back to {1:10,2:20,3:35,4:50,5:75}
            result = DefaultScoringEngine().calculate_xp(1, 5, 60)
            assert result == 20  # base=10, 2.0x

    def test_all_difficulty_levels_produce_positive_xp(self):
        for diff in range(1, 6):
            assert self.engine.calculate_xp(diff, 30, 60) > 0


class TestKIEScoringEngine:

    def test_kie_happy_path_returns_server_value(self):
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.requests.post",
                   return_value=_make_kie_response(42)):
            result = engine.calculate_xp(difficulty=2, time_taken=10, time_limit=60)
        assert result == 42

    def test_kie_failure_falls_back_to_default(self):
        from app.core.exceptions.exceptions import RulesException
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.RulesEngine") as mock_kie:
            mock_kie.execute.side_effect = RulesException()
            # difficulty=1, time_taken=5 → DefaultScoringEngine → 20
            result = engine.calculate_xp(difficulty=1, time_taken=5, time_limit=60)
        assert result == 20

    def test_kie_fallback_returns_int(self):
        from app.core.exceptions.exceptions import RulesException
        engine = KIEScoringEngine()
        with patch("app.services.rules_service.RulesEngine") as mock_kie:
            mock_kie.execute.side_effect = RulesException()
            result = engine.calculate_xp(difficulty=3, time_taken=20, time_limit=60)
        assert isinstance(result, int)


class TestGetScoringEngine:

    def setup_method(self):
        # Reset singleton before every test
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
