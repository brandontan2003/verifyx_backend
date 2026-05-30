"""
Unit tests for app.core.authentication.giggle.GiggleAuthProvider

Every method must raise NotImplementedError — this is the contract that
tells Giggle Academy's team which methods require implementation.
These tests guard against someone accidentally providing a partial
implementation that silently no-ops instead of signalling incompleteness.
"""
import pytest

from app.core.authentication.giggle import GiggleAuthProvider
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest


@pytest.fixture
def provider():
    return GiggleAuthProvider()


class TestGiggleProviderIsStub:

    def test_decode_token_raises(self, provider):
        with pytest.raises(NotImplementedError):
            provider.decode_token("any.jwt.token")

    @pytest.mark.asyncio
    async def test_validate_session_raises(self, provider):
        with pytest.raises(NotImplementedError):
            await provider.validate_session("any.jwt.token")

    @pytest.mark.asyncio
    async def test_sign_in_raises(self, provider):
        with pytest.raises(NotImplementedError):
            await provider.sign_in("user@example.com", "password123")

    @pytest.mark.asyncio
    async def test_sign_up_raises(self, provider):
        with pytest.raises(NotImplementedError):
            await provider.sign_up("newuser@example.com", "password123")

    @pytest.mark.asyncio
    async def test_refresh_token_raises(self, provider):
        with pytest.raises(NotImplementedError):
            await provider.refresh_token("some-refresh-token")

    @pytest.mark.asyncio
    async def test_revoke_token_raises(self, provider):
        with pytest.raises(NotImplementedError):
            await provider.revoke_token("any.jwt.token")

    @pytest.mark.asyncio
    async def test_send_reset_password_email_raises(self, provider):
        request = ResetPasswordRequest(email="user@example.com")
        with pytest.raises(NotImplementedError):
            await provider.send_reset_password_email(request, "https://app.example.com")

    @pytest.mark.asyncio
    async def test_update_user_password_raises(self, provider):
        request = UpdatePasswordRequest(email="user@example.com", password="newpass123", token="reset-token",
                                        confirmation_code=None)
        with pytest.raises(NotImplementedError):
            await provider.update_user_password(request)

    def test_all_errors_mention_giggle_provider(self, provider):
        """Every NotImplementedError message must identify the class so the stack trace is unambiguous."""
        try:
            provider.decode_token("x")
        except NotImplementedError as e:
            assert "GiggleAuthProvider" in str(e)

    def test_provider_is_auth_provider_subclass(self):
        from app.core.authentication_provider import AuthProvider
        assert issubclass(GiggleAuthProvider, AuthProvider)


class TestGetAuthProviderRouting:
    """get_auth_provider() must route AUTH_PROVIDER=giggle to GiggleAuthProvider."""

    def test_giggle_routes_to_giggle_provider(self):
        from unittest.mock import patch
        from app.dependencies import get_auth_provider
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.AUTH_PROVIDER = "giggle"
            provider = get_auth_provider()
        assert isinstance(provider, GiggleAuthProvider)

    def test_supabase_routes_to_supabase_provider(self):
        from unittest.mock import patch
        from app.dependencies import get_auth_provider
        from app.core.authentication.supabase import SupabaseAuthProvider
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.AUTH_PROVIDER = "supabase"
            provider = get_auth_provider()
        assert isinstance(provider, SupabaseAuthProvider)

    def test_unknown_value_falls_back_to_supabase(self):
        from unittest.mock import patch
        from app.dependencies import get_auth_provider
        from app.core.authentication.supabase import SupabaseAuthProvider
        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.AUTH_PROVIDER = "someunknownvalue"
            provider = get_auth_provider()
        assert isinstance(provider, SupabaseAuthProvider)
