import ast
from abc import ABC, abstractmethod

from app.config import settings
from app.core.logger import logger


class ScoringEngine(ABC):
    @abstractmethod
    def calculate_xp(self, difficulty: int, time_taken: int, time_limit: int) -> int:
        """
        Return XP earned for a completed challenge attempt.

        Args:
            difficulty:  1–5 as assigned by the AI scenario generator.
            time_taken:  Seconds the user took to answer.
            time_limit:  Total seconds allowed (typically 60).

        Returns:
            XP as a non-negative integer.
        """
        ...


class DefaultScoringEngine(ScoringEngine):
    """
    Rule-based XP engine. No external service required.

    Formula:
        base_xp = XP_TABLE[difficulty]  (env var, default {1:10,2:20,3:35,4:50,5:75})
        multiplier = speed band (see calculate_speed_multiplier below)
        xp = round(base_xp * multiplier)

    This replicates the KIE fallback logic that already exists in
    progress_service.py, promoted to a first-class engine so it can be
    selected deliberately rather than only on KIE failure.
    """

    def _xp_table(self) -> dict:
        try:
            return ast.literal_eval(settings.XP_TABLE)
        except Exception:
            logger.warning("XP_TABLE env var could not be parsed — using hardcoded defaults")
            return {1: 10, 2: 20, 3: 35, 4: 50, 5: 75}

    @staticmethod
    def _speed_multiplier(time_taken: int, time_limit: int) -> float:
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

    def calculate_xp(self, difficulty: int, time_taken: int, time_limit: int) -> int:
        base_xp = self._xp_table().get(difficulty, 10)
        multiplier = self._speed_multiplier(time_taken, time_limit)
        return round(base_xp * multiplier)


class KIEScoringEngine(ScoringEngine):
    """
    XP engine backed by the KIE/Drools DMN server.

    Falls back to DefaultScoringEngine on any KIE failure so that a
    Rules Engine outage does not break challenge submission.

    Note: RulesEngine.execute() uses synchronous requests. This is a
    known issue (blocks the event loop). Replace with httpx.AsyncClient
    if you move XP calculation into an async path — tracked separately.
    """

    def __init__(self):
        self._fallback = DefaultScoringEngine()

    def calculate_xp(self, difficulty: int, time_taken: int, time_limit: int) -> int:
        from app.core.exceptions.exceptions import RulesException
        from app.core.rules.rules_config import DecisionNameEnum, DmnRegistryKeyEnum
        from app.services.rules_service import RulesEngine, evaluate_result_list

        try:
            response = RulesEngine.execute(
                DmnRegistryKeyEnum.XP_DMN,
                [DecisionNameEnum.CALCULATE_XP],
                {"difficulty": difficulty, "time_taken": time_taken, "time_limit": time_limit},
            )
            return evaluate_result_list(response, DecisionNameEnum.CALCULATE_XP)
        except RulesException:
            logger.warning(
                "KIE XP calculation failed — falling back to DefaultScoringEngine "
                "(difficulty=%d, time_taken=%d, time_limit=%d)",
                difficulty, time_taken, time_limit
            )
            return self._fallback.calculate_xp(difficulty, time_taken, time_limit)


_engine: ScoringEngine | None = None


def get_scoring_engine() -> ScoringEngine:
    """
    Return the configured ScoringEngine singleton.

    SCORING_ENGINE=kie      → KIEScoringEngine (requires RULE_SERVER_URL)
    SCORING_ENGINE=default  → DefaultScoringEngine
    (absent)                → DefaultScoringEngine
    """
    global _engine
    if _engine is None:
        choice = settings.SCORING_ENGINE.strip().lower()
        if choice == "kie":
            _engine = KIEScoringEngine()
            logger.info("ScoringEngine: KIEScoringEngine")
        else:
            _engine = DefaultScoringEngine()
            logger.info("ScoringEngine: DefaultScoringEngine")
    return _engine
