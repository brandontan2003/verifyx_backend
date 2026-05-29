from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit.dependencies import read_rate_limit, submit_rate_limit
from app.core.scope.dependencies import require_scope
from app.dependencies import get_current_user, get_db
from app.dto.base import DataResponse
from app.dto.error import ErrorResponse
from app.dto.user import UserResponse, UpdateUsernameRequest
from app.enums.ErrorEnum import ErrorEnum
from app.enums.ScopeEnum import ScopeType
from app.services.user_service import get_user, update_user

router = APIRouter(prefix="/user", tags=["user"])


@router.get("", response_model=DataResponse[UserResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.USER_READ))],
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code},
                       404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code}})
async def retrieve_user(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_user(user, db)


@router.put("", response_model=DataResponse[UserResponse],
            dependencies=[Depends(submit_rate_limit), Depends(require_scope(ScopeType.USER_WRITE))],
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def update_username(payload: UpdateUsernameRequest, user=Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    return await update_user(user, payload, db)
