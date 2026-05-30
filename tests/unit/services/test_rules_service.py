from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import RulesException
from app.services.rules_service import (
    RulesEngine,
    evaluate_result_list,
    evaluate_rules_response,
)

DB = AsyncMock()


def _make_decision_info(decision_name="CalculateXP", status="SUCCEEDED", result=50):
    info = MagicMock()
    info.decision_name = decision_name
    info.status = status
    info.result = result
    return info


class TestEvaluateResultList:
    def test_returns_result_on_success(self):
        info = _make_decision_info("CalculateXP", "SUCCEEDED", 75)
        result = evaluate_result_list([info], "CalculateXP")
        assert result == 75

    def test_raises_rules_exception_on_failed_status(self):
        info = _make_decision_info("CalculateXP", "FAILED", None)
        with pytest.raises(RulesException):
            evaluate_result_list([info], "CalculateXP")

    def test_raises_rules_exception_when_decision_not_in_list(self):
        info = _make_decision_info("OtherDecision", "SUCCEEDED", 10)
        with pytest.raises(RulesException):
            evaluate_result_list([info], "CalculateXP")

    def test_returns_first_matching_decision(self):
        infos = [
            _make_decision_info("Other", "SUCCEEDED", 10),
            _make_decision_info("CalculateXP", "SUCCEEDED", 50),
        ]
        result = evaluate_result_list(infos, "CalculateXP")
        assert result == 50


class TestEvaluateRulesResponse:
    def _make_rules_response(self, decision_name="CalculateXP",
                             status="SUCCEEDED", result=50, type_="SUCCESS"):
        info = _make_decision_info(decision_name, status, result)
        response = MagicMock()
        response.type = type_
        response.result.dmn_evaluation_result.decision_results = {
            decision_name: info
        }
        return response

    def test_returns_list_of_results_on_success(self):
        response = self._make_rules_response()
        result = evaluate_rules_response(response, ["CalculateXP"])
        assert len(result) == 1
        assert result[0].decision_name == "CalculateXP"

    def test_raises_when_response_type_not_success(self):
        response = self._make_rules_response(type_="FAILURE")
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["CalculateXP"])

    def test_raises_when_requested_decision_not_in_results(self):
        response = self._make_rules_response("OtherDecision")
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["CalculateXP"])

    def test_raises_when_decision_result_is_none(self):
        info = _make_decision_info("CalculateXP", "SUCCEEDED", None)
        response = MagicMock()
        response.type = "SUCCESS"
        response.result.dmn_evaluation_result.decision_results = {"CalculateXP": info}
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["CalculateXP"])


class TestRulesEngineExecute:
    def test_raises_value_error_for_unknown_dmn(self):
        with pytest.raises(ValueError, match="not found in registry"):
            RulesEngine.execute("UNKNOWN_DMN", ["SomeDecision"], {})

    def test_raises_rules_exception_on_non_200_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("app.services.rules_service.requests.post", return_value=mock_response), \
                patch("app.services.rules_service.settings") as mock_settings:
            mock_settings.RULE_SERVER_URL = "http://localhost:8080"
            mock_settings.RULE_SERVER_USER = "admin"
            mock_settings.RULE_SERVER_PASSWORD = "password"
            with pytest.raises(RulesException):
                RulesEngine.execute("XP_DMN", ["CalculateXP"], {"difficulty": 3})

    def test_calls_post_with_correct_payload_structure(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        decision_info = {
            "messages": [],
            "decision-id": "dec-1",
            "decision-name": "CalculateXP",
            "result": 50,
            "status": "SUCCEEDED",
        }
        mock_response.json.return_value = {
            "type": "SUCCESS",
            "msg": "ok",
            "result": {
                "dmn-evaluation-result": {
                    "messages": [],
                    "model-namespace": "ns",
                    "model-name": "Xp",
                    "decision-name": "CalculateXP",
                    "dmn-context": {},
                    "decision-results": {"CalculateXP": decision_info},
                }
            },
        }

        with patch("app.services.rules_service.requests.post", return_value=mock_response) as mock_post, \
                patch("app.services.rules_service.settings") as mock_settings:
            mock_settings.RULE_SERVER_URL = "http://localhost:8080"
            mock_settings.RULE_SERVER_USER = "admin"
            mock_settings.RULE_SERVER_PASSWORD = "password"
            RulesEngine.execute("XP_DMN", ["CalculateXP"], {"difficulty": 3})

        called_payload = mock_post.call_args.kwargs["json"]
        assert called_payload["model-name"] == "Xp"
        assert called_payload["dmn-context"]["InputData"]["difficulty"] == 3
