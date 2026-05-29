from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class BaseDTO(BaseModel):
    model_config = {
        "from_attributes": True,
        "use_enum_values": True
    }


class SuccessResponse(BaseModel):
    status: str = "SUCCESS"


class DataResponse(SuccessResponse, Generic[T]):
    result: T


class HealthCheckDTO(BaseDTO):
    status: str
