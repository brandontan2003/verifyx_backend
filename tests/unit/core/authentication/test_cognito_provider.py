from unittest.mock import MagicMock, patch

import pytest
from jose import JWTError

from app.core.authentication.cognito import CognitoAuthProvider
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest


def _mock_settings(**kwargs):
    s = MagicMock()
    s.JWT_SIGNING_KEY = "signing-key"
    s.JWT_AUDIENCE = "authenticated"
    s.SUPABASE_URL = "https://proj.supabase.co"
    s.SUPABASE_SERVICE_KEY = "service-key"
    s.RESET_PASSWORD_ENDPOINT = "/reset-password"
    s.COGNITO_REGION = "ap-southeast-1"
    s.COGNITO_CLIENT_ID = "client-id"
    s.COGNITO_USER_POOL_ID = "ap-southeast-1_pool"
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def _cognito_provider():
    provider = CognitoAuthProvider()
    return provider


def _mock_cognito_client():
    return MagicMock()


def _client_error(code="NotAuthorizedException", message="Wrong credentials"):
    from botocore.exceptions import ClientError
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "InitiateAuth"
    )


class TestCognitoDecodeToken:
    def test_returns_payload_on_valid_token(self):
        provider = _cognito_provider()
        expected = {"sub": "user-42", "cognito:username": "alice"}

        with patch("app.core.authentication.cognito.jwt.decode", return_value=expected), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = provider.decode_token("valid.jwt")

        assert result == expected

    def test_returns_none_on_jwt_error(self):
        provider = _cognito_provider()

        with patch("app.core.authentication.cognito.jwt.decode", side_effect=JWTError("bad")), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = provider.decode_token("bad.token")

        assert result is None

    def test_uses_rs256_only(self):
        provider = _cognito_provider()

        with patch("app.core.authentication.cognito.jwt.decode", return_value={}) as mock_decode, \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            provider.decode_token("tok")

        _, kwargs = mock_decode.call_args
        assert kwargs["algorithms"] == ["RS256"]

    def test_uses_jwt_audience_from_settings(self):
        provider = _cognito_provider()
        s = _mock_settings(JWT_AUDIENCE="cognito-audience")

        with patch("app.core.authentication.cognito.jwt.decode", return_value={}) as mock_decode, \
                patch("app.core.authentication.cognito.settings", s):
            provider.decode_token("tok")

        _, kwargs = mock_decode.call_args
        assert kwargs["audience"] == "cognito-audience"


class TestCognitoValidateSession:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = await provider.validate_session("valid-access-token")

        mock_boto.get_user.assert_called_once_with(AccessToken="valid-access-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_client_error(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.get_user.side_effect = _client_error("NotAuthorizedException")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = await provider.validate_session("expired-token")

        assert result is False

    @pytest.mark.asyncio
    async def test_raises_on_unexpected_non_client_error(self):
        """validate_session only catches ClientError; other exceptions propagate."""
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.get_user.side_effect = RuntimeError("boto3 internal crash")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            with pytest.raises(RuntimeError):
                await provider.validate_session("any-token")


class TestCognitoSignIn:
    @pytest.mark.asyncio
    async def test_returns_access_and_refresh_token(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "cog-access",
                "RefreshToken": "cog-refresh"
            }
        }

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = await provider.sign_in("user@email.com", "pass")

        assert result["access_token"] == "cog-access"
        assert result["refresh_token"] == "cog-refresh"

    @pytest.mark.asyncio
    async def test_uses_user_password_auth_flow(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {"AccessToken": "at", "RefreshToken": "rt"}
        }

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            await provider.sign_in("user@email.com", "pass")

        call_kwargs = mock_boto.initiate_auth.call_args.kwargs
        assert call_kwargs["AuthFlow"] == "USER_PASSWORD_AUTH"
        assert call_kwargs["AuthParameters"]["USERNAME"] == "user@email.com"
        assert call_kwargs["AuthParameters"]["PASSWORD"] == "pass"

    @pytest.mark.asyncio
    async def test_raises_client_error_on_failure(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.side_effect = _client_error("NotAuthorizedException")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            from botocore.exceptions import ClientError
            with pytest.raises(ClientError):
                await provider.sign_in("bad@email.com", "wrong")


class TestCognitoSignUp:
    @pytest.mark.asyncio
    async def test_sign_up_confirm_and_sign_in_called_in_order(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {"AccessToken": "at", "RefreshToken": "rt"}
        }

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = await provider.sign_up("new@email.com", "pass123")

        mock_boto.sign_up.assert_called_once()
        mock_boto.admin_confirm_sign_up.assert_called_once_with(
            UserPoolId="ap-southeast-1_pool",
            Username="new@email.com"
        )
        # sign_in via initiate_auth
        mock_boto.initiate_auth.assert_called_once()
        assert result["access_token"] == "at"

    @pytest.mark.asyncio
    async def test_sign_up_sets_email_attribute(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {"AccessToken": "at", "RefreshToken": "rt"}
        }

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            await provider.sign_up("new@email.com", "pass123")

        call_kwargs = mock_boto.sign_up.call_args.kwargs
        attrs = call_kwargs["UserAttributes"]
        assert any(a["Name"] == "email" and a["Value"] == "new@email.com" for a in attrs)

    @pytest.mark.asyncio
    async def test_raises_on_client_error(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.sign_up.side_effect = _client_error("UsernameExistsException")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            from botocore.exceptions import ClientError
            with pytest.raises(ClientError):
                await provider.sign_up("taken@email.com", "pass")


class TestCognitoRefreshToken:
    @pytest.mark.asyncio
    async def test_returns_new_access_token_and_original_refresh_token(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "new-access",
                # Cognito does NOT return a RefreshToken in REFRESH_TOKEN_AUTH
            }
        }

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            result = await provider.refresh_token("my-refresh-tok")

        assert result["access_token"] == "new-access"
        # Original refresh token must be preserved unchanged
        assert result["refresh_token"] == "my-refresh-tok"

    @pytest.mark.asyncio
    async def test_uses_refresh_token_auth_flow(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {"AccessToken": "at"}
        }

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            await provider.refresh_token("refresh-tok")

        call_kwargs = mock_boto.initiate_auth.call_args.kwargs
        assert call_kwargs["AuthFlow"] == "REFRESH_TOKEN_AUTH"
        assert call_kwargs["AuthParameters"]["REFRESH_TOKEN"] == "refresh-tok"

    @pytest.mark.asyncio
    async def test_raises_on_client_error(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.initiate_auth.side_effect = _client_error("NotAuthorizedException")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            from botocore.exceptions import ClientError
            with pytest.raises(ClientError):
                await provider.refresh_token("bad-refresh")


class TestCognitoRevokeToken:
    @pytest.mark.asyncio
    async def test_calls_revoke_with_token_and_client_id(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            await provider.revoke_token("access-token-999")

        mock_boto.revoke_token.assert_called_once_with(
            Token="access-token-999",
            ClientId="client-id"
        )

    @pytest.mark.asyncio
    async def test_swallows_exception_and_logs(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.revoke_token.side_effect = Exception("network error")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()), \
                patch("app.core.authentication.cognito.logger") as mock_log:
            await provider.revoke_token("any-token")  # must not raise

        mock_log.error.assert_called_once()


class TestCognitoSendResetPasswordEmail:
    @pytest.mark.asyncio
    async def test_calls_forgot_password_with_email_and_client_id(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            req = ResetPasswordRequest(email="user@example.com")
            await provider.send_reset_password_email(req, "https://myapp.com")

        mock_boto.forgot_password.assert_called_once_with(
            Username="user@example.com",
            ClientId="client-id"
        )

    @pytest.mark.asyncio
    async def test_swallows_exception_and_logs(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.forgot_password.side_effect = Exception("ses down")

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()), \
                patch("app.core.authentication.cognito.logger") as mock_log:
            req = ResetPasswordRequest(email="user@example.com")
            await provider.send_reset_password_email(req, "https://myapp.com")

        mock_log.error.assert_called_once()


class TestCognitoUpdateUserPassword:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_confirmation_code_missing(self):
        provider = _cognito_provider()
        req = UpdatePasswordRequest(email="u@b.com", password="newpass")

        with pytest.raises(ValueError, match="confirmation code"):
            await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_calls_confirm_forgot_password_with_correct_args(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        req = UpdatePasswordRequest(
            email="u@b.com", password="newpass", confirmation_code="654321"
        )

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            await provider.update_user_password(req)

        mock_boto.confirm_forgot_password.assert_called_once_with(
            Username="u@b.com",
            ConfirmationCode="654321",
            Password="newpass",
            ClientId="client-id"
        )

    @pytest.mark.asyncio
    async def test_raises_client_error_on_invalid_code(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.confirm_forgot_password.side_effect = _client_error(
            "CodeMismatchException", "Invalid verification code"
        )
        req = UpdatePasswordRequest(
            email="u@b.com", password="newpass", confirmation_code="000000"
        )

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            from botocore.exceptions import ClientError
            with pytest.raises(ClientError):
                await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_raises_client_error_on_expired_code(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.confirm_forgot_password.side_effect = _client_error(
            "ExpiredCodeException", "Code has expired"
        )
        req = UpdatePasswordRequest(
            email="u@b.com", password="newpass", confirmation_code="123456"
        )

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            from botocore.exceptions import ClientError
            with pytest.raises(ClientError):
                await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_re_raises_unexpected_exception(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        mock_boto.confirm_forgot_password.side_effect = RuntimeError("boto3 crash")
        req = UpdatePasswordRequest(
            email="u@b.com", password="newpass", confirmation_code="123456"
        )

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            with pytest.raises(RuntimeError, match="boto3 crash"):
                await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_succeeds_without_raising_on_valid_code(self):
        provider = _cognito_provider()
        mock_boto = _mock_cognito_client()
        req = UpdatePasswordRequest(
            email="u@b.com", password="secure123", confirmation_code="123456"
        )

        with patch.object(provider, "_client", return_value=mock_boto), \
                patch("app.core.authentication.cognito.settings", _mock_settings()):
            await provider.update_user_password(req)  # should not raise
