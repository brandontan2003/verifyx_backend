from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.rate_limit.dependencies import read_rate_limit, submit_rate_limit
from app.core.scope.dependencies import require_scope
from app.dependencies import get_current_user, get_db
from app.dto.base import DataResponse
from app.dto.error import ErrorResponse
from app.dto.progress import UpdateProgressResponse, UpdateProgressRequest, UserProgressResponse
from app.enums.ErrorEnum import ErrorEnum
from app.enums.ScopeEnum import ScopeType
from app.services.progress_service import get_user_progress, update_progress

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("", response_model=DataResponse[UpdateProgressResponse],
             dependencies=[Depends(submit_rate_limit), Depends(require_scope(ScopeType.PROGRESS_WRITE))],
             responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                        404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def submit_progress(payload: UpdateProgressRequest, user=Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    result = await update_progress(user["sub"], payload, db)
    return DataResponse(result=result)


@router.get("", response_model=DataResponse[UserProgressResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.PROGRESS_READ))],
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def retrieve_progress(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_user_progress(user["sub"], db)
    return DataResponse(result=result)
