from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError

from app.core.authentication.supabase import SupabaseAuthProvider
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


def _supabase_session(access="at-123", refresh="rt-456"):
    session = MagicMock()
    session.session.access_token = access
    session.session.refresh_token = refresh
    return session


class TestSupabaseDecodeToken:
    def test_returns_payload_on_valid_token(self):
        provider = SupabaseAuthProvider()
        expected = {"sub": "user-1", "email": "a@b.com"}

        with patch("app.core.authentication.supabase.jwt.decode", return_value=expected), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = provider.decode_token("valid.jwt.token")

        assert result == expected

    def test_returns_none_on_jwt_error(self):
        provider = SupabaseAuthProvider()

        with patch("app.core.authentication.supabase.jwt.decode", side_effect=JWTError("bad")), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = provider.decode_token("bad.token")

        assert result is None

    def test_uses_rs256_and_es256_algorithms(self):
        provider = SupabaseAuthProvider()

        with patch("app.core.authentication.supabase.jwt.decode", return_value={}) as mock_decode, \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            provider.decode_token("tok")

        _, kwargs = mock_decode.call_args
        assert "RS256" in kwargs["algorithms"]
        assert "ES256" in kwargs["algorithms"]

    def test_uses_jwt_audience_from_settings(self):
        provider = SupabaseAuthProvider()
        s = _mock_settings(JWT_AUDIENCE="my-audience")

        with patch("app.core.authentication.supabase.jwt.decode", return_value={}) as mock_decode, \
                patch("app.core.authentication.supabase.settings", s):
            provider.decode_token("tok")

        _, kwargs = mock_decode.call_args
        assert kwargs["audience"] == "my-audience"


class TestSupabaseValidateSession:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        provider = SupabaseAuthProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = await provider.validate_session("valid-token")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self):
        provider = SupabaseAuthProvider()
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = await provider.validate_session("expired-token")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_network_error(self):
        provider = SupabaseAuthProvider()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=ConnectionError("timeout"))

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = await provider.validate_session("any-token")

        assert result is False

    @pytest.mark.asyncio
    async def test_sends_bearer_and_apikey_headers(self):
        provider = SupabaseAuthProvider()
        mock_response = MagicMock(status_code=200)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.validate_session("my-token")

        _, kwargs = mock_client.get.call_args
        headers = kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-token"
        assert headers["apikey"] == "service-key"


class TestSupabaseSignIn:
    @pytest.mark.asyncio
    async def test_returns_access_and_refresh_token(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.sign_in_with_password.return_value = _supabase_session("at-abc", "rt-xyz")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = await provider.sign_in("user@email.com", "pass")

        assert result["access_token"] == "at-abc"
        assert result["refresh_token"] == "rt-xyz"

    @pytest.mark.asyncio
    async def test_raises_on_supabase_failure(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.sign_in_with_password.side_effect = Exception("invalid credentials")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            with pytest.raises(Exception, match="invalid credentials"):
                await provider.sign_in("bad@email.com", "wrong")

    @pytest.mark.asyncio
    async def test_calls_sign_in_with_email_and_password(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.sign_in_with_password.return_value = _supabase_session()

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.sign_in("user@email.com", "mypass")

        mock_client.auth.sign_in_with_password.assert_called_once_with(
            {"email": "user@email.com", "password": "mypass"}
        )


class TestSupabaseSignUp:
    @pytest.mark.asyncio
    async def test_returns_tokens_on_success(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.sign_up.return_value = _supabase_session("at-new", "rt-new")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = await provider.sign_up("new@email.com", "pass123")

        assert result["access_token"] == "at-new"
        assert result["refresh_token"] == "rt-new"

    @pytest.mark.asyncio
    async def test_raises_on_supabase_failure(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.sign_up.side_effect = Exception("email taken")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            with pytest.raises(Exception, match="email taken"):
                await provider.sign_up("taken@email.com", "pass")


class TestSupabaseRefreshToken:
    @pytest.mark.asyncio
    async def test_returns_new_tokens(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.refresh_session.return_value = _supabase_session("at-fresh", "rt-fresh")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            result = await provider.refresh_token("old-refresh-token")

        assert result["access_token"] == "at-fresh"
        assert result["refresh_token"] == "rt-fresh"

    @pytest.mark.asyncio
    async def test_passes_refresh_token_to_supabase(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.refresh_session.return_value = _supabase_session()

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.refresh_token("my-refresh-token")

        mock_client.auth.refresh_session.assert_called_once_with("my-refresh-token")

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.refresh_session.side_effect = Exception("expired")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            with pytest.raises(Exception, match="expired"):
                await provider.refresh_token("bad-token")


class TestSupabaseRevokeToken:
    @pytest.mark.asyncio
    async def test_calls_admin_sign_out(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.revoke_token("access-token-123")

        mock_client.auth.admin.sign_out.assert_called_once_with("access-token-123")

    @pytest.mark.asyncio
    async def test_swallows_exception_and_logs(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.admin.sign_out.side_effect = Exception("network error")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()), \
                patch("app.core.authentication.supabase.logger") as mock_log:
            await provider.revoke_token("any-token")  # must not raise

        mock_log.error.assert_called_once()


class TestSupabaseSendResetPasswordEmail:
    @pytest.mark.asyncio
    async def test_calls_reset_with_email_and_redirect_url(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        s = _mock_settings(RESET_PASSWORD_ENDPOINT="/reset-password")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", s):
            req = ResetPasswordRequest(email="user@example.com")
            await provider.send_reset_password_email(req, "https://myapp.com")

        mock_client.auth.reset_password_for_email.assert_called_once_with(
            "user@example.com",
            options={"redirect_to": "https://myapp.com/reset-password"}
        )

    @pytest.mark.asyncio
    async def test_swallows_exception_and_logs(self):
        provider = SupabaseAuthProvider()
        mock_client = MagicMock()
        mock_client.auth.reset_password_for_email.side_effect = Exception("smtp down")

        with patch("app.core.authentication.supabase.create_client", return_value=mock_client), \
                patch("app.core.authentication.supabase.settings", _mock_settings()), \
                patch("app.core.authentication.supabase.logger") as mock_log:
            req = ResetPasswordRequest(email="user@example.com")
            await provider.send_reset_password_email(req, "https://myapp.com")

        mock_log.error.assert_called_once()


class TestSupabaseUpdateUserPassword:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_token_missing(self):
        provider = SupabaseAuthProvider()
        req = UpdatePasswordRequest(email="u@b.com", password="newpass")

        with pytest.raises(ValueError, match="token"):
            await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_succeeds_on_200_response(self):
        provider = SupabaseAuthProvider()
        req = UpdatePasswordRequest(email="u@b.com", password="newpass", token="reset-token")

        mock_response = MagicMock(status_code=200)
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.put = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_http), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.update_user_password(req)  # should not raise

    @pytest.mark.asyncio
    async def test_succeeds_on_204_response(self):
        provider = SupabaseAuthProvider()
        req = UpdatePasswordRequest(email="u@b.com", password="newpass", token="reset-token")

        mock_response = MagicMock(status_code=204)
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.put = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_http), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_non_200_non_204(self):
        provider = SupabaseAuthProvider()
        req = UpdatePasswordRequest(email="u@b.com", password="newpass", token="bad-token")

        mock_response = MagicMock(status_code=422)
        mock_response.json.return_value = {"msg": "Token expired or invalid"}

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.put = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_http), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            with pytest.raises(RuntimeError, match="Token expired or invalid"):
                await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_re_raises_unexpected_exception(self):
        provider = SupabaseAuthProvider()
        req = UpdatePasswordRequest(email="u@b.com", password="newpass", token="tok")

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.put = AsyncMock(side_effect=ConnectionError("network failure"))

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_http), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            with pytest.raises(ConnectionError):
                await provider.update_user_password(req)

    @pytest.mark.asyncio
    async def test_sends_correct_headers_and_body(self):
        provider = SupabaseAuthProvider()
        req = UpdatePasswordRequest(email="u@b.com", password="mynewpass", token="reset-tok")

        mock_response = MagicMock(status_code=200)
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.put = AsyncMock(return_value=mock_response)

        with patch("app.core.authentication.supabase.httpx.AsyncClient", return_value=mock_http), \
                patch("app.core.authentication.supabase.settings", _mock_settings()):
            await provider.update_user_password(req)

        _, kwargs = mock_http.put.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer reset-tok"
        assert kwargs["headers"]["apikey"] == "service-key"
        assert kwargs["json"]["password"] == "mynewpass"
        call_url = mock_http.put.call_args[0][0]
        assert "/auth/v1/user" in call_url
