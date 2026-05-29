from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import UserAlreadyExistsException, UserNotFoundException
from app.dto.user import UpdateUsernameRequest
from app.services.user_service import (
    create_user,
    get_user,
    retrieve_user,
    retrieve_user_by_email,
    update_user,
)

DB = AsyncMock()

AUTH_USER = {"sub": "uid-001", "email": "jane.doe@example.com"}


def _make_db_user(user_id="uid-001", email="jane.doe@example.com", username="jane.doe"):
    u = MagicMock()
    u.user_id = user_id
    u.email = email
    u.username = username
    u.xp = 0
    u.streak = 0
    return u


def _make_repo(get_by_user_id_result=None, get_by_email_result=None, create_result=None, update_result=None):
    repo = AsyncMock()
    repo.get_by_user_id.return_value = get_by_user_id_result
    repo.get_by_email.return_value = get_by_email_result
    repo.create.return_value = create_result or _make_db_user()
    repo.update_username.return_value = update_result or _make_db_user(username="newname")
    return repo


class TestRetrieveUser:
    async def test_returns_user_when_found(self):
        db_user = _make_db_user()
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=db_user)):
            result = await retrieve_user(DB, AUTH_USER)

        assert result.user_id == "uid-001"

    async def test_returns_none_when_not_found(self):
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=None)):
            result = await retrieve_user(DB, AUTH_USER)

        assert result is None

    async def test_uses_sub_from_auth_payload(self):
        repo = _make_repo()
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await retrieve_user(DB, {"sub": "uid-specific", "email": "x@x.com"})

        repo.get_by_user_id.assert_called_once_with("uid-specific")


class TestRetrieveUserByEmail:
    async def test_returns_user_when_found(self):
        db_user = _make_db_user()
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_email_result=db_user)):
            result = await retrieve_user_by_email("jane.doe@example.com", DB)

        assert result.email == "jane.doe@example.com"

    async def test_returns_none_when_not_found(self):
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_email_result=None)):
            result = await retrieve_user_by_email("ghost@example.com", DB)

        assert result is None

    async def test_passes_email_to_repo(self):
        repo = _make_repo()
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await retrieve_user_by_email("specific@test.com", DB)

        repo.get_by_email.assert_called_once_with("specific@test.com")


class TestGetUser:
    async def test_returns_data_response_wrapping_user(self):
        db_user = _make_db_user()
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=db_user)):
            result = await get_user(AUTH_USER, DB)

        assert result.result.user_id == "uid-001"

    async def test_raises_user_not_found_when_missing(self):
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=None)):
            with pytest.raises(UserNotFoundException):
                await get_user(AUTH_USER, DB)

    async def test_does_not_raise_when_user_exists(self):
        db_user = _make_db_user()
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=db_user)):
            result = await get_user(AUTH_USER, DB)

        assert result is not None


class TestCreateUser:
    async def test_raises_already_exists_for_duplicate_sub(self):
        existing = _make_db_user()
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=existing)):
            with pytest.raises(UserAlreadyExistsException):
                await create_user(AUTH_USER, DB)

    async def test_derives_username_from_email_prefix(self):
        repo = _make_repo(get_by_user_id_result=None)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await create_user({"sub": "uid-001", "email": "jane.doe@example.com"}, DB)

        repo.create.assert_called_once_with("uid-001", "jane.doe@example.com", "jane.doe")

    async def test_handles_email_with_multiple_at_signs_gracefully(self):
        """split('@')[0] should always take the local part before the first @."""
        repo = _make_repo(get_by_user_id_result=None)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await create_user({"sub": "uid-002", "email": "user@subdomain@example.com"}, DB)

        call_args = repo.create.call_args
        assert call_args[0][2] == "user"  # username = part before first @

    async def test_returns_data_response_wrapping_created_user(self):
        created = _make_db_user(user_id="uid-new", username="newuser")
        repo = _make_repo(get_by_user_id_result=None, create_result=created)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            result = await create_user({"sub": "uid-new", "email": "newuser@test.com"}, DB)

        assert result.result.user_id == "uid-new"

    async def test_calls_repo_create_with_correct_sub_and_email(self):
        repo = _make_repo(get_by_user_id_result=None)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await create_user({"sub": "uid-abc", "email": "specific@test.com"}, DB)

        repo.create.assert_called_once_with("uid-abc", "specific@test.com", "specific")


class TestUpdateUser:
    async def test_raises_user_not_found_when_user_missing(self):
        with patch("app.services.user_service.UserRepository",
                   return_value=_make_repo(get_by_user_id_result=None)):
            with pytest.raises(UserNotFoundException):
                await update_user(
                    AUTH_USER,
                    UpdateUsernameRequest(username="newname"),
                    DB
                )

    async def test_calls_repo_update_with_correct_args(self):
        existing = _make_db_user()
        repo = _make_repo(get_by_user_id_result=existing)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await update_user(
                {"sub": "uid-001", "email": "x@x.com"},
                UpdateUsernameRequest(username="newname"),
                DB
            )

        repo.update_username.assert_called_once_with("uid-001", "newname")

    async def test_returns_data_response_wrapping_updated_user(self):
        existing = _make_db_user()
        updated = _make_db_user(username="newname")
        repo = _make_repo(get_by_user_id_result=existing, update_result=updated)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            result = await update_user(
                AUTH_USER,
                UpdateUsernameRequest(username="newname"),
                DB
            )

        assert result.result.username == "newname"

    async def test_does_not_update_other_users(self):
        """update_user must use the sub from the auth payload, not any user-supplied ID."""
        existing = _make_db_user(user_id="uid-001")
        repo = _make_repo(get_by_user_id_result=existing)
        with patch("app.services.user_service.UserRepository", return_value=repo):
            await update_user(
                {"sub": "uid-001", "email": "x@x.com"},
                UpdateUsernameRequest(username="newname"),
                DB
            )

        call_args = repo.update_username.call_args
        assert call_args[0][0] == "uid-001"  # user_id from JWT, not payload
