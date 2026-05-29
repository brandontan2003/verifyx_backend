from typing import Optional

from app.dto.base import BaseDTO


class ErrorDetail(BaseDTO):
    error_code: str
    error_message: str
    field_name: Optional[str] = None


class ErrorResult(BaseDTO):
    errors: list[ErrorDetail]


class ErrorResponse(BaseDTO):
    status: str = "ERROR"
    result: ErrorResult
    path: Optional[str] = None
