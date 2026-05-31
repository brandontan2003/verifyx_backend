from fastapi import APIRouter, Depends

from app.core.cache.rate_limit.dependencies import read_rate_limit
from app.dto.base import DataResponse
from app.dto.code import RetrieveThemeResponse
from app.dto.error import ErrorResponse
from app.enums.ErrorEnum import ErrorEnum
from app.services.code_service import retrieve_theme_service

router = APIRouter(prefix="/code", tags=["code"])


@router.get("/theme", response_model=DataResponse[RetrieveThemeResponse],
            dependencies=[Depends(read_rate_limit)],
            responses={422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code},
                       404: {"model": ErrorResponse, "description": ErrorEnum.CODE_NOT_FOUND.error_code}})
async def retrieve_theme():
    return DataResponse(result=retrieve_theme_service())
