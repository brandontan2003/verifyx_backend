import requests

from app.config import settings
from app.core.exceptions.exceptions import RulesException
from app.core.rules.rules_config import DMN_REGISTRY
from app.core.rules.rules_dto import RulesResponse


def evaluate_result_list(result_list: list, decision_name: str):
    for info in result_list:
        if info.decision_name == decision_name:
            if info.status == "SUCCEEDED":
                return info.result
            else:
                raise RulesException()
    raise RulesException()


def evaluate_rules_response(response: RulesResponse, decision_names: list):
    if response.type != "SUCCESS":
        raise RulesException()
    all_results = response.result.dmn_evaluation_result.decision_results.values()

    successful_results = {
        info.decision_name: info
        for info in all_results if info.status == "SUCCEEDED" and info.result is not None
    }

    results_list = []
    for name in decision_names:
        if name in successful_results:
            results_list.append(successful_results[name])
        else:
            # If a requested decision failed or wasn't found, raise an exception
            raise RulesException()

    if results_list is None or len(results_list) == 0:
        raise RulesException()
    return results_list


class RulesEngine:
    @staticmethod
    def execute(dmn_name: str, decision_name: list, request: dict):
        config = DMN_REGISTRY.get(dmn_name)
        if not config:
            raise ValueError(f"Rule {dmn_name} not found in registry")

        url = (f"{settings.RULE_SERVER_URL}/services/rest/server/containers/"
               f"{config['container_id']}/dmn")

        # 3. Construct the Standard KIE Payload
        payload = {
            "model-namespace": config["model_namespace"],
            "model-name": config["model_name"],
            "decision-name": decision_name,
            "dmn-context": {
                "InputData": request
            }
        }

        # 4. Request with Auth
        response = requests.post(
            url,
            json=payload,
            auth=(settings.RULE_SERVER_USER, settings.RULE_SERVER_PASSWORD),
            headers={"Content-Type": "application/json", "Accept": "application/json"}
        )

        if response.status_code != 200:
            raise RulesException()

        dmn_output = RulesResponse.model_validate(response.json())
        return evaluate_rules_response(dmn_output, decision_name)
