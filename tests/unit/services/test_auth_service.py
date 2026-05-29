from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import (
    InvalidCredentialsException,
    LogoutFailedException,
    SignUpFailedException,
    UserAlreadyExistsException,
    UserNotFoundException,
    PasswordResetFailedException,
)
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest
from app.services.auth_service import (
    logout_user,
    refresh_user_token,
    signin_user,
    signup_user,
    update_user_password,
    user_forget_password,
)

DB = AsyncMock()


def _make_provider(sign_in_result=None, sign_up_result=None, decode_result=None, sign_in_raises=None,
                   sign_up_raises=None, refresh_raises=None, revoke_raises=None, reset_raises=None, update_raises=None):
    p = MagicMock()
    if sign_in_raises:
        p.sign_in = AsyncMock(side_effect=sign_in_raises)
    else:
        p.sign_in = AsyncMock(return_value=sign_in_result or {"access_token": "at", "refresh_token": "rt"})
    if sign_up_raises:
        p.sign_up = AsyncMock(side_effect=sign_up_raises)
    else:
        p.sign_up = AsyncMock(return_value=sign_up_result or {"access_token": "at", "refresh_token": "rt"})
    if refresh_raises:
        p.refresh_token = AsyncMock(side_effect=refresh_raises)
    else:
        p.refresh_token = AsyncMock(return_value={"access_token": "new_at", "refresh_token": "new_rt"})
    if revoke_raises:
        p.revoke_token = AsyncMock(side_effect=revoke_raises)
    else:
        p.revoke_token = AsyncMock(return_value=None)
    if reset_raises:
        p.send_reset_password_email = AsyncMock(side_effect=reset_raises)
    else:
        p.send_reset_password_email = AsyncMock(return_value=None)
    if update_raises:
        p.update_user_password = AsyncMock(side_effect=update_raises)
    else:
        p.update_user_password = AsyncMock(return_value=None)
    p.decode_token = MagicMock(return_value=decode_result or {"sub": "uid-001", "email": "test@test.com"})
    return p


MOCK_USER = {"user_id": "uid-001", "email": "test@test.com", "username": "tester"}


class TestSigninUser:
    async def test_returns_tokens_and_user(self):
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)), \
                patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
            result = await signin_user("test@test.com", "pass", DB)

        assert result["access_token"] == "at"
        assert result["refresh_token"] == "rt"
        assert result["user"] == MOCK_USER

    async def test_raises_user_not_found_when_not_in_db(self):
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundException):
                await signin_user("ghost@test.com", "pass", DB)

    async def test_raises_invalid_credentials_on_provider_error(self):
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)), \
                patch("app.services.auth_service.get_auth_provider",
                      return_value=_make_provider(sign_in_raises=Exception("wrong password"))):
            with pytest.raises(InvalidCredentialsException):
                await signin_user("test@test.com", "wrong", DB)

    async def test_user_not_found_is_not_caught_as_invalid_credentials(self):
        """UserNotFoundException must propagate as 404, not be swallowed as 401."""
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundException):
                await signin_user("ghost@test.com", "pass", DB)


class TestSignupUser:
    async def test_raises_already_exists_for_duplicate_email(self):
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)):
            with pytest.raises(UserAlreadyExistsException):
                await signup_user("test@test.com", "pass", DB)

    async def test_calls_create_user_and_logs_out_on_success(self):
        provider = _make_provider()
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=None)), \
                patch("app.services.auth_service.get_auth_provider", return_value=provider), \
                patch("app.services.auth_service.create_user", AsyncMock(return_value=MOCK_USER)) as mock_create, \
                patch("app.services.auth_service.logout_user", AsyncMock(return_value=None)) as mock_logout:
            await signup_user("new@test.com", "pass", DB)

        mock_create.assert_called_once()
        mock_logout.assert_called_once()

    async def test_raises_signup_failed_on_provider_error(self):
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=None)), \
                patch("app.services.auth_service.get_auth_provider",
                      return_value=_make_provider(sign_up_raises=Exception("provider down"))):
            with pytest.raises(SignUpFailedException):
                await signup_user("new@test.com", "pass", DB)

    async def test_already_exists_not_swallowed_as_signup_failed(self):
        """UserAlreadyExistsException must propagate as 400, not be caught as SignUpFailedException."""
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)):
            with pytest.raises(UserAlreadyExistsException):
                await signup_user("test@test.com", "pass", DB)


class TestRefreshUserToken:
    async def test_returns_new_tokens(self):
        with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
            result = await refresh_user_token("old_rt")

        assert result["access_token"] == "new_at"
        assert result["refresh_token"] == "new_rt"

    async def test_raises_invalid_credentials_on_provider_error(self):
        with patch("app.services.auth_service.get_auth_provider",
                   return_value=_make_provider(refresh_raises=Exception("token expired"))):
            with pytest.raises(InvalidCredentialsException):
                await refresh_user_token("bad_token")


class TestLogoutUser:
    async def test_calls_provider_revoke_with_token(self):
        provider = _make_provider()
        with patch("app.services.auth_service.get_auth_provider", return_value=provider):
            await logout_user("access_token", {"sub": "uid-001"})

        provider.revoke_token.assert_called_once_with("access_token")

    async def test_raises_logout_failed_on_provider_error(self):
        with patch("app.services.auth_service.get_auth_provider",
                   return_value=_make_provider(revoke_raises=Exception("network error"))):
            with pytest.raises(LogoutFailedException):
                await logout_user("token", {"sub": "uid-001"})


class TestUserForgetPassword:
    async def test_calls_provider_send_reset_email(self):
        provider = _make_provider()
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)), \
                patch("app.services.auth_service.get_auth_provider", return_value=provider):
            await user_forget_password(ResetPasswordRequest(email="test@test.com"), DB, "http://test")

        provider.send_reset_password_email.assert_called_once()

    async def test_not_found_is_not_silenced(self):
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundException):
                await user_forget_password(ResetPasswordRequest(email="ghost@test.com"), DB, "http://test")

    async def test_provider_error_raises_reset_failed(self):
        """
        ⚠️  This test will also FAIL until the bug above is fixed,
        because the bare except swallows provider errors silently too.
        """
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)), \
                patch("app.services.auth_service.get_auth_provider",
                      return_value=_make_provider(reset_raises=Exception("provider down"))):
            with pytest.raises(PasswordResetFailedException):
                await user_forget_password(ResetPasswordRequest(email="test@test.com"), DB, "http://test")


class TestUpdateUserPassword:
    async def test_checks_user_exists(self):
        provider = _make_provider()
        payload = UpdatePasswordRequest(
            email="test@test.com", password="NewPass1!", confirmation_code="123456"
        )
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)), \
                patch("app.services.auth_service.get_auth_provider", return_value=provider):
            await update_user_password(payload, DB)

        provider.update_user_password.assert_called_once_with(payload)

    async def test_raises_not_found_when_user_missing(self):
        payload = UpdatePasswordRequest(
            email="ghost@test.com", password="NewPass1!", confirmation_code="123456"
        )
        with patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundException):
                await update_user_password(payload, DB)

    async def test_raises_reset_failed_on_provider_error(self):
        payload = UpdatePasswordRequest(email="test@test.com", password="NewPass1!", token="tok")
        with patch("app.services.auth_service.get_auth_provider",
                   return_value=_make_provider(update_raises=Exception("provider error"))), \
                patch("app.services.auth_service.retrieve_user_by_email", AsyncMock(return_value=MOCK_USER)):
            with pytest.raises(PasswordResetFailedException):
                await update_user_password(payload, DB)
