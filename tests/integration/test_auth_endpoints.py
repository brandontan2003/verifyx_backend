"""
Integration tests for /api/v1/auth endpoints.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from app.enums.ErrorEnum import ErrorEnum
from app.models.user import User
from tests.conftest import AppTestClient, _seed_user, assert_error, get_response_data

# Test data
SIGNUP_PAYLOAD = {"email": "new@test.com", "password": "SecurePass1!"}
SIGNIN_PAYLOAD = {"email": "existing@test.com", "password": "SecurePass1!"}
AUTH_USER = {"sub": "existing-uid-0001", "email": "existing@test.com"}


def _make_provider(sign_in_result=None, sign_up_result=None, sign_in_raises=None, sign_up_raises=None,
                   refresh_raises=None, revoke_raises=None, reset_raises=None, update_raises=None, decode_result=None):
    p = MagicMock()
    p.sign_in = AsyncMock(
        return_value=sign_in_result or {"access_token": "test-access-token", "refresh_token": "test-refresh-token"},
        side_effect=sign_in_raises,
    )
    p.sign_up = AsyncMock(
        return_value=sign_up_result or {"access_token": "test-access-token", "refresh_token": "test-refresh-token"},
        side_effect=sign_up_raises,
    )
    p.refresh_token = AsyncMock(
        return_value={"access_token": "new-access-token", "refresh_token": "new-refresh-token"},
        side_effect=refresh_raises,
    )
    p.revoke_token = AsyncMock(return_value=None, side_effect=revoke_raises)
    p.send_reset_password_email = AsyncMock(return_value=None, side_effect=reset_raises)
    p.update_user_password = AsyncMock(return_value=None, side_effect=update_raises)
    p.decode_token = MagicMock(
        return_value=decode_result or {"sub": "new-uid-0001", "email": "new@test.com"}
    )
    p.validate_session = AsyncMock(return_value=True)
    return p


# Test Sign Up
class TestSignup:
    async def test_returns_200_on_success(self, db_session):
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()), \
                    patch("app.services.auth_service.logout_user", AsyncMock()):
                response = await client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    async def test_creates_user_in_db(self, db_session):
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider(
                    decode_result={"sub": "new-uid-0001", "email": "new@test.com"}
            )), patch("app.services.auth_service.logout_user", AsyncMock()):
                await client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)

        result = await db_session.execute(select(User).where(User.email == "new@test.com"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "new@test.com"
        assert user.username == "new"

    async def test_new_user_has_user_role(self, db_session):
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()), \
                    patch("app.services.auth_service.logout_user", AsyncMock()):
                await client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)

        result = await db_session.execute(select(User).where(User.email == "new@test.com"))
        user = result.scalar_one_or_none()
        assert user.role_id == "role-user-id-0001"

    async def test_returns_400_for_duplicate_email(self, db_session):
        await _seed_user(db_session, email="new@test.com")

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
        assert_error(response, ErrorEnum.USER_ALREADY_EXISTS, 400)

    async def test_returns_422_for_missing_email(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/signup", json={"password": "SecurePass1!"})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_422_for_missing_password(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/signup", json={"email": "x@test.com"})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_422_for_empty_body(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/signup", json={})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)


# Test Sign In
class TestSignin:
    async def test_returns_200_with_user_data(self, db_session):
        await _seed_user(db_session, username="existinguser")

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post("/api/v1/auth/signin", json=SIGNIN_PAYLOAD)

        result = await db_session.execute(select(User).where(User.email == "existing@test.com"))
        user = result.scalar_one_or_none()
        expected_result = {
            "user_id": user.user_id,
            "email": "existing@test.com",
            "username": "existinguser",
            "xp": 0,
            "streak": 0
        }

        assert response.status_code == 200
        assert get_response_data(response) == expected_result

    async def test_sets_access_token_cookie(self, db_session):
        await _seed_user(db_session)

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post("/api/v1/auth/signin", json=SIGNIN_PAYLOAD)

        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    async def test_sets_refresh_token_cookie(self, db_session):
        await _seed_user(db_session)

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post("/api/v1/auth/signin", json=SIGNIN_PAYLOAD)

        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    async def test_returns_404_for_unknown_email(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post(
                "/api/v1/auth/signin",
                json={"email": "ghost@test.com", "password": "pass"}
            )
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_401_on_wrong_password(self, db_session):
        await _seed_user(db_session)

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider",
                       return_value=_make_provider(sign_in_raises=Exception("wrong password"))):
                response = await client.post("/api/v1/auth/signin", json=SIGNIN_PAYLOAD)
        assert_error(response, ErrorEnum.INVALID_CREDENTIALS, 401)

    async def test_returns_422_for_missing_fields(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/signin", json={})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)


# Test Refresh Token
class TestRefresh:
    async def test_returns_200_and_rotates_cookies(self, db_session):
        # refresh does not need get_current_user — it reads the cookie directly
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post(
                    "/api/v1/auth/refresh",
                    cookies={"refresh_token": "valid-refresh-token"}
                )

        assert response.status_code == 200
        assert "access_token" in response.cookies

    async def test_returns_401_when_no_refresh_cookie(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/refresh")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)

    async def test_returns_401_on_expired_token(self, db_session):
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider",
                       return_value=_make_provider(refresh_raises=Exception("token expired"))):
                response = await client.post(
                    "/api/v1/auth/refresh",
                    cookies={"refresh_token": "expired-token"}
                )
        assert_error(response, ErrorEnum.INVALID_CREDENTIALS, 401)


#  Test Logout
class TestLogout:
    async def test_returns_200_when_authenticated(self, db_session):
        """Logout requires an authenticated user — AppTestClient is initialised with auth_user."""
        async with AppTestClient(db_session, auth_user=AUTH_USER) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post(
                    "/api/v1/auth/logout",
                    cookies={"access_token": "test-access-token"}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    async def test_clears_cookies_on_logout(self, db_session):
        async with AppTestClient(db_session, auth_user=AUTH_USER) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post(
                    "/api/v1/auth/logout",
                    cookies={"access_token": "test-access-token"}
                )

        # Cookie is cleared — value is empty or absent
        assert response.cookies.get("access_token") in (None, "")

    async def test_returns_401_without_auth(self, db_session):
        """No auth_user passed — get_current_user runs normally and returns 401."""
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/logout")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Test Forget Password
class TestForgetPassword:
    async def test_returns_200_for_existing_user(self, db_session):
        await _seed_user(db_session, email="reset@test.com")

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post(
                    "/api/v1/auth/forget/password",
                    json={"email": "reset@test.com"}
                )
        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    async def test_returns_404_for_unknown_email(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post(
                "/api/v1/auth/forget/password",
                json={"email": "ghost@test.com"}
            )
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_422_for_missing_email(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/auth/forget/password", json={})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_does_not_require_authentication(self, db_session):
        """forget/password is a public endpoint — no auth_user needed."""
        await _seed_user(db_session, email="reset2@test.com")

        async with AppTestClient(db_session) as client:  # no auth_user
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post(
                    "/api/v1/auth/forget/password",
                    json={"email": "reset2@test.com"}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"


# Test Update Password
class TestUpdatePassword:
    async def test_supabase_path_returns_200(self, db_session):
        """Supabase path — token in body, no email needed."""
        await _seed_user(db_session)
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.put(
                    "/api/v1/auth/update/password",
                    json={"email": "existing@test.com", "password": "NewPass1!", "token": "supabase-reset-token"}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    async def test_cognito_path_returns_200(self, db_session):
        """Cognito path — email + confirmation_code in body."""
        await _seed_user(db_session, email="cognito@test.com")

        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.put(
                    "/api/v1/auth/update/password",
                    json={
                        "email": "cognito@test.com",
                        "password": "NewPass1!",
                        "confirmation_code": "123456"
                    }
                )

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    async def test_cognito_path_returns_404_for_unknown_email(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.put(
                "/api/v1/auth/update/password",
                json={
                    "email": "ghost@test.com",
                    "password": "NewPass1!",
                    "confirmation_code": "123456"
                }
            )
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_422_for_missing_password(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.put(
                "/api/v1/auth/update/password",
                json={"token": "some-token"}
            )
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_does_not_require_authentication(self, db_session):
        """update/password is a public endpoint — the reset token proves identity."""
        await _seed_user(db_session, email="existing@test.com")
        async with AppTestClient(db_session) as client:  # no auth_user
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.put(
                    "/api/v1/auth/update/password",
                    json={"email": "existing@test.com", "password": "NewPass1!", "token": "supabase-reset-token"}
                )

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"


# Test Rate limiting
class TestRateLimit:
    async def test_returns_429_when_limit_exceeded(self, db_session, mock_redis):
        mock_redis._state.force_limit = True

        async with AppTestClient(db_session) as client:
            response = await client.post(
                "/api/v1/auth/signin",
                json=SIGNIN_PAYLOAD
            )
        assert_error(response, ErrorEnum.RATE_LIMIT_EXCEEDED, 429)

    async def test_does_not_rate_limit_under_threshold(self, db_session):
        async with AppTestClient(db_session) as client:
            with patch("app.services.auth_service.get_auth_provider", return_value=_make_provider()):
                response = await client.post(
                    "/api/v1/auth/forget/password",
                    json={"email": "ghost@test.com"}
                )

        assert response.status_code != 429
