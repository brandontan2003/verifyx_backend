from fastapi import APIRouter, Depends

from app.core.rate_limit.dependencies import ai_rate_limit
from app.dependencies import get_current_user
from app.dto.base import DataResponse
from app.dto.error import ErrorResponse
from app.dto.news import (
    VerifyRequest,
    VerifyResponse,
)
from app.enums.ErrorEnum import ErrorEnum
from app.services.verify_service import verify_content

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/verify", response_model=DataResponse[VerifyResponse], dependencies=[Depends(ai_rate_limit)],
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code},
                 429: {"model": ErrorResponse, "description": ErrorEnum.RATE_LIMIT_EXCEEDED.error_code},
             })
async def verify(payload: VerifyRequest, user=Depends(get_current_user)):
    result = await verify_content(payload)
    return DataResponse(result=result)
