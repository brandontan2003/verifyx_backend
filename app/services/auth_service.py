from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import (
    LogoutFailedException,
    InvalidCredentialsException,
    SignUpFailedException,
    UserNotFoundException, UserAlreadyExistsException, PasswordResetFailedException
)
from app.core.logger import logger
from app.dependencies import get_auth_provider
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest
from app.enums.ErrorEnum import ErrorEnum
from app.services.user_service import create_user, retrieve_user_by_email


async def signin_user(email: str, password: str, database: AsyncSession) -> dict:
    try:
        provider = get_auth_provider()

        # Check user exists in DB — if not, FE should redirect to signup
        user = await retrieve_user_by_email(email, database)
        if not user:
            raise UserNotFoundException()

        tokens = await provider.sign_in(email, password)

        return {**tokens, "user": user}
    except UserNotFoundException:
        raise
    except Exception as ex:
        logger.error("Sign in failed for %s: %s", email, ex, exc_info=True)
        raise InvalidCredentialsException()


async def signup_user(email: str, password: str, database: AsyncSession) -> None:
    try:
        provider = get_auth_provider()

        # Check user exists in DB — if exists, FE should redirect to signin
        user_existing = await retrieve_user_by_email(email, database)
        if user_existing:
            raise UserAlreadyExistsException()

        tokens = await provider.sign_up(email, password)
        access_token = tokens["access_token"]
        # Decode token to get user payload
        payload = provider.decode_token(access_token)

        # Create user in DB immediately after signup.
        # IMPORTANT:
        # create_user() does NOT return a User directly.
        # It returns DataResponse(status=..., result=User).
        # Always extract the user via response.result before using it.
        user = await create_user(payload, database)

        await logout_user(access_token, user)
    except UserAlreadyExistsException:
        raise
    except Exception as ex:
        logger.error("Sign up failed for %s: %s", email, ex, exc_info=True)
        raise SignUpFailedException()


async def refresh_user_token(refresh_token: str) -> dict:
    try:
        provider = get_auth_provider()
        return await provider.refresh_token(refresh_token)
    except Exception as ex:
        logger.error("Token refresh failed: %s", ex, exc_info=True)
        raise InvalidCredentialsException()


async def logout_user(token: str, user: dict) -> None:
    try:
        provider = get_auth_provider()
        await provider.revoke_token(token)
    except Exception as ex:
        logger.error("Logout failed for user %s: %s", user.get("sub"), ex, exc_info=True)
        raise LogoutFailedException()


async def user_forget_password(request: ResetPasswordRequest, database: AsyncSession, origin: str):
    try:
        user = await retrieve_user_by_email(request.email, database)
        if not user:
            raise UserNotFoundException()

        provider = get_auth_provider()
        await provider.send_reset_password_email(request, origin)
    except UserNotFoundException:
        raise
    except Exception as ex:
        logger.error("Failed to sent reset password email for user %s: %s", request.email, ex, exc_info=True)
        raise PasswordResetFailedException()


async def update_user_password(request: UpdatePasswordRequest, database: AsyncSession):
    try:
        user = await retrieve_user_by_email(request.email, database)
        if not user:
            raise UserNotFoundException()

        provider = get_auth_provider()
        await provider.update_user_password(request)
    except UserNotFoundException:
        raise
    except ValueError as ex:
        logger.error("Password update rejected — missing field: %s", ex)
        error_message = str(ex) if ex is not None else ErrorEnum.PASSWORD_RESET_FAILED.error_message
        raise PasswordResetFailedException(error_message)
    except Exception as ex:
        logger.error("Failed to update password for user %s: %s", request.email, ex, exc_info=True)
        error_message = str(ex) if ex is not None else ErrorEnum.PASSWORD_RESET_FAILED.error_message
        raise PasswordResetFailedException(error_message)
