from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import RulesException
from app.core.rules.rules_config import DecisionNameEnum, DmnRegistryKeyEnum
from app.services.rules_service import (
    RulesEngine,
    evaluate_result_list,
    evaluate_rules_response,
)


def _make_dmn_result_info(decision_name: str, result, status: str = "SUCCEEDED") -> dict:
    return {
        "messages": [],
        "decision-id": "_BE7648BE-F382-4DA4-9DF8-4C3FECC79DA0",
        "decision-name": decision_name,
        "result": result,
        "status": status,
    }


def _make_kie_json(xp_value: int, decision_name: str = "CalculateXP",
                   response_type: str = "SUCCESS") -> dict:
    """Build a full KIE JSON response as the server would return it."""
    return {
        "type": response_type,
        "msg": "OK",
        "result": {
            "dmn-evaluation-result": {
                "messages": [],
                "model-namespace": "https://kiegroup.org/dmn/_43BF0ABF",
                "model-name": "Xp",
                "decision-name": decision_name,
                "dmn-context": {
                    "InputData": {"difficulty": 1, "time_taken": 5, "time_limit": 60},
                    decision_name: xp_value,
                },
                "decision-results": {
                    "_BE7648BE": _make_dmn_result_info(decision_name, xp_value),
                },
            }
        },
    }


def _make_mock_info(decision_name: str, result, status: str = "SUCCEEDED"):
    """Build a mock DMNDecisionResultInfo object (as returned by evaluate_rules_response)."""
    info = MagicMock()
    info.decision_name = decision_name
    info.result = result
    info.status = status
    return info


def _make_httpx_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    return resp


class TestEvaluateResultList:

    def test_returns_result_for_matching_succeeded_decision(self):
        info = _make_mock_info("CalculateXP", 42)
        result = evaluate_result_list([info], "CalculateXP")
        assert result == 42

    def test_raises_when_decision_status_is_not_succeeded(self):
        info = _make_mock_info("CalculateXP", None, status="FAILED")
        with pytest.raises(RulesException):
            evaluate_result_list([info], "CalculateXP")

    def test_raises_when_decision_name_not_in_list(self):
        info = _make_mock_info("CalculateXP", 42)
        with pytest.raises(RulesException):
            evaluate_result_list([info], "NonExistentDecision")

    def test_raises_on_empty_list(self):
        with pytest.raises(RulesException):
            evaluate_result_list([], "CalculateXP")

    def test_returns_first_match_when_multiple_decisions(self):
        infos = [
            _make_mock_info("CalculateSpeedMultiplier", 2.0),
            _make_mock_info("CalculateXP", 100),
        ]
        assert evaluate_result_list(infos, "CalculateXP") == 100

    def test_result_can_be_zero(self):
        info = _make_mock_info("CalculateXP", 0)
        result = evaluate_result_list([info], "CalculateXP")
        assert result == 0

    def test_result_can_be_float(self):
        info = _make_mock_info("CalculateSpeedMultiplier", 1.5)
        result = evaluate_result_list([info], "CalculateSpeedMultiplier")
        assert result == 1.5


class TestEvaluateRulesResponse:

    def _make_response_obj(self, xp_value: int, response_type: str = "SUCCESS",
                           status: str = "SUCCEEDED", result=None):
        from app.core.rules.rules_dto import RulesResponse
        body = _make_kie_json(xp_value if result is None else result,
                              response_type=response_type)
        if status != "SUCCEEDED":
            dr = body["result"]["dmn-evaluation-result"]["decision-results"]
            dr["_BE7648BE"]["status"] = status
        return RulesResponse.model_validate(body)

    def test_returns_result_list_on_success(self):
        from app.core.rules.rules_dto import RulesResponse
        response = RulesResponse.model_validate(_make_kie_json(42))
        result = evaluate_rules_response(response, ["CalculateXP"])
        assert len(result) == 1
        assert result[0].result == 42

    def test_raises_when_response_type_is_not_success(self):
        from app.core.rules.rules_dto import RulesResponse
        response = RulesResponse.model_validate(_make_kie_json(42, response_type="FAILURE"))
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["CalculateXP"])

    def test_raises_when_requested_decision_not_in_results(self):
        from app.core.rules.rules_dto import RulesResponse
        response = RulesResponse.model_validate(_make_kie_json(42))
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["NonExistentDecision"])

    def test_raises_when_decision_result_is_null(self):
        from app.core.rules.rules_dto import RulesResponse
        body = _make_kie_json(42)
        # Null result — evaluate_rules_response filters these out
        body["result"]["dmn-evaluation-result"]["decision-results"]["_BE7648BE"]["result"] = None
        response = RulesResponse.model_validate(body)
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["CalculateXP"])

    def test_raises_when_decision_status_is_failed(self):
        from app.core.rules.rules_dto import RulesResponse
        body = _make_kie_json(42)
        body["result"]["dmn-evaluation-result"]["decision-results"]["_BE7648BE"]["status"] = "FAILED"
        response = RulesResponse.model_validate(body)
        with pytest.raises(RulesException):
            evaluate_rules_response(response, ["CalculateXP"])


class TestRulesEngineExecute:

    def _patch_httpx(self, status_code: int, body: dict):
        """
        Patch httpx.AsyncClient so that client.post() returns a mock response.
        We patch at the module level (app.services.rules_service.httpx) so the
        patch targets the exact import used by rules_service.py.
        """
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(status_code, body)
        )
        mock_async_ctx = AsyncMock()
        mock_async_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_async_ctx
        return mock_httpx, mock_client

    @pytest.mark.asyncio
    async def test_happy_path_returns_result_list(self):
        mock_httpx, mock_client = self._patch_httpx(200, _make_kie_json(42))
        with patch("app.services.rules_service.httpx", mock_httpx):
            result = await RulesEngine.execute(
                DmnRegistryKeyEnum.XP_DMN,
                [DecisionNameEnum.CALCULATE_XP],
                {"difficulty": 1, "time_taken": 5, "time_limit": 60},
            )
        assert len(result) == 1
        assert result[0].result == 42
        assert result[0].decision_name == "CalculateXP"

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self):
        mock_httpx, mock_client = self._patch_httpx(200, _make_kie_json(20))
        with patch("app.services.rules_service.httpx", mock_httpx), \
                patch("app.services.rules_service.settings") as mock_settings:
            mock_settings.RULE_SERVER_URL = "http://kie-server:8080"
            mock_settings.RULE_SERVER_USER = "user"
            mock_settings.RULE_SERVER_PASSWORD = "pass"
            await RulesEngine.execute(
                DmnRegistryKeyEnum.XP_DMN,
                [DecisionNameEnum.CALCULATE_XP],
                {"difficulty": 1, "time_taken": 5, "time_limit": 60},
            )
        call_args = mock_client.post.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url") or call_args.args[0]
        assert "code_exp26_rules" in url
        assert "dmn" in url

    @pytest.mark.asyncio
    async def test_raises_rules_exception_on_non_200(self):
        mock_httpx, _ = self._patch_httpx(500, {})
        with patch("app.services.rules_service.httpx", mock_httpx):
            with pytest.raises(RulesException):
                await RulesEngine.execute(
                    DmnRegistryKeyEnum.XP_DMN,
                    [DecisionNameEnum.CALCULATE_XP],
                    {"difficulty": 1, "time_taken": 5, "time_limit": 60},
                )

    @pytest.mark.asyncio
    async def test_raises_rules_exception_on_404(self):
        mock_httpx, _ = self._patch_httpx(404, {})
        with patch("app.services.rules_service.httpx", mock_httpx):
            with pytest.raises(RulesException):
                await RulesEngine.execute(
                    DmnRegistryKeyEnum.XP_DMN,
                    [DecisionNameEnum.CALCULATE_XP],
                    {},
                )

    @pytest.mark.asyncio
    async def test_raises_value_error_on_unknown_dmn_key(self):
        with pytest.raises(ValueError, match="not found in registry"):
            await RulesEngine.execute(
                "NONEXISTENT_DMN",
                [DecisionNameEnum.CALCULATE_XP],
                {},
            )

    @pytest.mark.asyncio
    async def test_raises_rules_exception_on_kie_failure_response(self):
        """KIE returns 200 but type=FAILURE — evaluate_rules_response raises."""
        mock_httpx, _ = self._patch_httpx(200, _make_kie_json(0, response_type="FAILURE"))
        with patch("app.services.rules_service.httpx", mock_httpx):
            with pytest.raises(RulesException):
                await RulesEngine.execute(
                    DmnRegistryKeyEnum.XP_DMN,
                    [DecisionNameEnum.CALCULATE_XP],
                    {"difficulty": 1, "time_taken": 5, "time_limit": 60},
                )

    @pytest.mark.asyncio
    async def test_request_payload_contains_dmn_context(self):
        """Payload sent to KIE must wrap the request dict inside dmn-context.InputData."""
        mock_httpx, mock_client = self._patch_httpx(200, _make_kie_json(20))
        input_data = {"difficulty": 3, "time_taken": 20, "time_limit": 60}
        with patch("app.services.rules_service.httpx", mock_httpx):
            await RulesEngine.execute(
                DmnRegistryKeyEnum.XP_DMN,
                [DecisionNameEnum.CALCULATE_XP],
                input_data,
            )
        call_kwargs = mock_client.post.call_args.kwargs
        payload = call_kwargs.get("json") or mock_client.post.call_args.args[1]
        assert payload["dmn-context"]["InputData"] == input_data
        assert payload["decision-name"] == [DecisionNameEnum.CALCULATE_XP]

    @pytest.mark.asyncio
    async def test_request_has_10s_timeout(self):
        mock_httpx, mock_client = self._patch_httpx(200, _make_kie_json(20))
        with patch("app.services.rules_service.httpx", mock_httpx):
            await RulesEngine.execute(
                DmnRegistryKeyEnum.XP_DMN,
                [DecisionNameEnum.CALCULATE_XP],
                {},
            )
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs.get("timeout") == 10.0
