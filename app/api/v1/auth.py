from fastapi import APIRouter, Depends, Cookie, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache.rate_limit.dependencies import auth_rate_limit
from app.dependencies import get_current_user, get_db
from app.dto.auth import SignInRequest, SignUpRequest, ResetPasswordRequest, UpdatePasswordRequest
from app.dto.base import DataResponse, SuccessResponse
from app.dto.error import ErrorResponse
from app.dto.user import UserResponse
from app.enums.ErrorEnum import ErrorEnum
from app.services.auth_service import signin_user, signup_user, refresh_user_token, logout_user, user_forget_password, \
    update_user_password

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_CONFIG = {
    "httponly": True,
    "secure": True,  # HTTPS only — set to False for local dev if needed
    "samesite": "none",
    "max_age": 3600,  # 1 hour — matches JWT expiry
}


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(key="access_token", value=access_token, **COOKIE_CONFIG)
    response.set_cookie(key="refresh_token", value=refresh_token, max_age=604800, httponly=True, secure=True,
                        samesite="none")


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/signup", response_model=SuccessResponse,
             dependencies=[Depends(auth_rate_limit)],
             responses={400: {"model": ErrorResponse, "description": ErrorEnum.SIGNUP_FAILED.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def signup(payload: SignUpRequest, db: AsyncSession = Depends(get_db)):
    await signup_user(payload.email, payload.password, db)
    return SuccessResponse()


@router.post("/signin", response_model=DataResponse[UserResponse],
             dependencies=[Depends(auth_rate_limit)],
             responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_CREDENTIALS.error_code},
                        404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def signin(payload: SignInRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await signin_user(payload.email, payload.password, db)
    set_auth_cookies(response, result["access_token"], result["refresh_token"])
    return DataResponse(result=result["user"])


@router.post("/refresh", response_model=SuccessResponse,
             dependencies=[Depends(auth_rate_limit)],
             responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def refresh(response: Response, refresh_token: str = Cookie(default=None)):
    if not refresh_token:
        from app.core.exceptions.exceptions import InvalidTokenException
        raise InvalidTokenException()
    tokens = await refresh_user_token(refresh_token)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return SuccessResponse()


@router.post("/logout", response_model=SuccessResponse,
             dependencies=[Depends(auth_rate_limit)],
             responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code},
                        500: {"model": ErrorResponse, "description": ErrorEnum.LOGOUT_FAILED.error_code}})
async def logout(response: Response, user=Depends(get_current_user), access_token: str = Cookie(default=None)):
    await logout_user(access_token, user)
    clear_auth_cookies(response)
    return SuccessResponse()


@router.post("/forget/password", response_model=SuccessResponse,
             dependencies=[Depends(auth_rate_limit)],
             responses={404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def forget_password(payload: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    origin = request.headers.get("origin") or settings.FRONTEND_URL_LIST[0]
    await user_forget_password(payload, db, origin)
    return SuccessResponse()


@router.put("/update/password", response_model=SuccessResponse,
            dependencies=[Depends(auth_rate_limit)],
            responses={404: {"model": ErrorResponse, "description": ErrorEnum.USER_NOT_FOUND.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def update_password(payload: UpdatePasswordRequest, db: AsyncSession = Depends(get_db)):
    await update_user_password(payload, db)
    return SuccessResponse()
