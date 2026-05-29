from typing import List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class DMNDecisionResultInfo(BaseModel):
    messages: List[Any]
    decision_id: str = Field(alias="decision-id")
    decision_name: str = Field(alias="decision-name")
    result: Any
    status: str

    model_config = ConfigDict(populate_by_name=True)


class DmnEvaluationResult(BaseModel):
    messages: List[Any]
    model_namespace: str = Field(alias="model-namespace")
    model_name: str = Field(alias="model-name")
    decision_name: str = Field(alias="decision-name")
    # dmn_context is dynamic, but we can type hint the expected keys
    dmn_context: Dict[str, Any] = Field(alias="dmn-context")
    decision_results: Dict[str, DMNDecisionResultInfo] = Field(alias="decision-results")

    model_config = ConfigDict(populate_by_name=True)


class RulesResultWrapper(BaseModel):
    dmn_evaluation_result: DmnEvaluationResult = Field(alias="dmn-evaluation-result")

    model_config = ConfigDict(populate_by_name=True)


class RulesResponse(BaseModel):
    type: str
    msg: str
    result: RulesResultWrapper
