from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import logger
from app.dto.error import ErrorResponse, ErrorResult, ErrorDetail
from app.enums.ErrorEnum import ErrorEnum

err = ErrorEnum


class BaseAppException(Exception):
    def __init__(self, status_code: int, error_code: str, error_message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.error_message = error_message


class UserAlreadyExistsException(BaseAppException):
    def __init__(self):
        super().__init__(400, err.USER_ALREADY_EXISTS.error_code, err.USER_ALREADY_EXISTS.error_message)


class UserNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.USER_NOT_FOUND.error_code, err.USER_NOT_FOUND.error_message)


class BadgeNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.BADGE_NOT_FOUND.error_code, err.BADGE_NOT_FOUND.error_message)


class InvalidTokenException(BaseAppException):
    def __init__(self):
        super().__init__(401, err.INVALID_TOKEN.error_code, err.INVALID_TOKEN.error_message)


class CommonException(BaseAppException):
    pass


class LogoutFailedException(BaseAppException):
    def __init__(self):
        super().__init__(500, err.LOGOUT_FAILED.error_code, err.LOGOUT_FAILED.error_message)


class InvalidCredentialsException(BaseAppException):
    def __init__(self):
        super().__init__(401, err.INVALID_CREDENTIALS.error_code, err.INVALID_CREDENTIALS.error_message)


class SignUpFailedException(BaseAppException):
    def __init__(self):
        super().__init__(400, err.SIGNUP_FAILED.error_code, err.SIGNUP_FAILED.error_message)


class ChallengeNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.CHALLENGE_NOT_FOUND.error_code, err.CHALLENGE_NOT_FOUND.error_message)


class ChallengeAlreadySubmittedException(BaseAppException):
    def __init__(self):
        super().__init__(409, err.CHALLENGE_ALREADY_SUBMITTED.error_code, err.CHALLENGE_ALREADY_SUBMITTED.error_message)


class RoomNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.ROOM_NOT_FOUND.error_code, err.ROOM_NOT_FOUND.error_message)


class RoomFullException(BaseAppException):
    def __init__(self):
        super().__init__(409, err.ROOM_FULL.error_code, err.ROOM_FULL.error_message)


class RoomAlreadyActiveException(BaseAppException):
    def __init__(self):
        super().__init__(409, err.ROOM_ALREADY_ACTIVE.error_code, err.ROOM_ALREADY_ACTIVE.error_message)


class NotRoomHostException(BaseAppException):
    def __init__(self):
        super().__init__(403, err.NOT_ROOM_HOST.error_code, err.NOT_ROOM_HOST.error_message)


class AlreadyInRoomException(BaseAppException):
    def __init__(self):
        super().__init__(409, err.ALREADY_IN_ROOM.error_code, err.ALREADY_IN_ROOM.error_message)


class RoomNotActiveException(BaseAppException):
    def __init__(self):
        super().__init__(409, err.ROOM_NOT_ACTIVE.error_code, err.ROOM_NOT_ACTIVE.error_message)


class InvalidAnswerFormatException(BaseAppException):
    def __init__(self):
        super().__init__(422, err.INVALID_ANSWER_FORMAT.error_code, err.INVALID_ANSWER_FORMAT.error_message)


class PasswordResetFailedException(BaseAppException):
    def __init__(self, detail: str = None):
        message = detail if detail is not None else err.PASSWORD_RESET_FAILED.error_message
        super().__init__(400, err.PASSWORD_RESET_FAILED.error_code, message)


class RateLimitExceededException(BaseAppException):
    def __init__(self, headers: dict = None):
        super().__init__(429, err.RATE_LIMIT_EXCEEDED.error_code, err.RATE_LIMIT_EXCEEDED.error_message)
        self.headers = headers or {}


class RulesException(BaseAppException):
    def __init__(self, headers: dict = None):
        super().__init__(500, err.RULES_EXECUTION_FAILURE.error_code, err.RULES_EXECUTION_FAILURE.error_message)
        self.headers = headers or {}


class ScopeForbiddenException(BaseAppException):
    def __init__(self):
        super().__init__(403, err.SCOPE_FORBIDDEN.error_code, err.SCOPE_FORBIDDEN.error_message)


class RoleForbiddenException(BaseAppException):
    def __init__(self):
        super().__init__(403, err.ROLE_FORBIDDEN.error_code, err.ROLE_FORBIDDEN.error_message)


class ReportNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.REPORT_NOT_FOUND.error_code, err.REPORT_NOT_FOUND.error_message)


class DailyChallengeLimitException(BaseAppException):
    def __init__(self):
        super().__init__(429, err.DAILY_CHALLENGE_LIMIT.error_code, err.DAILY_CHALLENGE_LIMIT.error_message)


class NewsPostNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.NEWS_POST_NOT_FOUND.error_code, err.NEWS_POST_NOT_FOUND.error_message)


class CommentNotFoundException(BaseAppException):
    def __init__(self):
        super().__init__(404, err.COMMENT_NOT_FOUND.error_code, err.COMMENT_NOT_FOUND.error_message)


class CommentDepthExceededException(BaseAppException):
    def __init__(self):
        super().__init__(422, err.COMMENT_DEPTH_EXCEEDED.error_code, err.COMMENT_DEPTH_EXCEEDED.error_message)


class ReportTerminalStateException(BaseAppException):
    def __init__(self):
        super().__init__(409, err.REPORT_TERMINAL_STATE.error_code, err.REPORT_TERMINAL_STATE.error_message)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Map common HTTP status codes to error codes
        error_code_map = {
            404: err.NOT_FOUND.error_code,
            405: err.METHOD_NOT_ALLOWED.error_code,
            403: err.FORBIDDEN.error_code,
            500: err.INTERNAL_SERVER_ERROR.error_code,
        }
        error_code = error_code_map.get(exc.status_code, err.HTTP_ERROR.error_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                result=ErrorResult(errors=[
                    ErrorDetail(
                        error_code=error_code,
                        error_message=str(exc.detail)
                    )
                ]),
                path=str(request.url.path)
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        details = [
            ErrorDetail(
                error_code=err.VALIDATION_ERROR.error_code,
                error_message=error['msg'],
                field_name=f"{error['loc'][0]}.{error['loc'][-1]}" if len(error['loc']) > 1 else str(error['loc'][0])
            )
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                result=ErrorResult(errors=details),
                path=str(request.url.path)
            ).model_dump()
        )

    @app.exception_handler(BaseAppException)
    async def app_exception_handler(request: Request, exc: BaseAppException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                result=ErrorResult(errors=[
                    ErrorDetail(error_code=exc.error_code, error_message=exc.error_message)
                ]),
                path=str(request.url.path)
            ).model_dump()
        )

    # @app.exception_handler(Exception)
    # async def unhandled_exception_handler(request: Request, exc: Exception):
    #     error = ErrorResponse(
    #         result=ErrorResult(errors=[
    #             ErrorDetail(error_code=err.INTERNAL_SERVER_ERROR.error_code,
    #                         error_message=err.INTERNAL_SERVER_ERROR.error_message)
    #         ]),
    #         path=str(request.url.path)
    #     )
    #     return JSONResponse(status_code=500, content=error.model_dump())
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s", request.url.path)

        error = ErrorResponse(
            result=ErrorResult(errors=[
                ErrorDetail(
                    error_code=err.INTERNAL_SERVER_ERROR.error_code,
                    error_message=err.INTERNAL_SERVER_ERROR.error_message
                )
            ]),
            path=str(request.url.path)
        )
        return JSONResponse(status_code=500, content=error.model_dump())
