from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import ScopeForbiddenException, UserNotFoundException
from app.core.scope.dependencies import require_scope
from app.enums.ScopeEnum import ScopeType
from app.models.user import User


def _make_db_user(user_id: str = "uid-001", role_id: str = "role-user-001") -> User:
    user = MagicMock(spec=User)
    user.user_id = user_id
    user.role_id = role_id
    return user


async def _invoke_scope_check(required_scopes: tuple[ScopeType, ...], jwt_payload: dict, db_user: User | None,
                              role_scopes: list[ScopeType]) -> None:
    """
    Execute the inner _check_scope dependency directly,
    bypassing FastAPI's DI wiring.
    """
    mock_db = AsyncMock(spec=AsyncSession)

    mock_user_repo = AsyncMock()
    mock_user_repo.get_by_user_id = AsyncMock(return_value=db_user)

    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_scopes = AsyncMock(return_value=role_scopes)

    # Extract the inner coroutine function from the factory
    inner = require_scope(*required_scopes)

    with patch("app.core.scope.dependencies.UserRepository", return_value=mock_user_repo), \
            patch("app.core.scope.dependencies.RoleRepository", return_value=mock_role_repo):
        await inner(user=jwt_payload, db=mock_db)


class TestRequireScopeAllowed:

    @pytest.mark.asyncio
    async def test_single_scope_present_passes(self):
        user = _make_db_user()
        await _invoke_scope_check(
            required_scopes=(ScopeType.CHALLENGE_READ,),
            jwt_payload={"sub": "uid-001"},
            db_user=user,
            role_scopes=[ScopeType.CHALLENGE_READ, ScopeType.ROOM_READ],
        )

    @pytest.mark.asyncio
    async def test_any_of_multiple_scopes_passes(self):
        """require_scope(A, B) — user only has B → should pass (OR logic)."""
        user = _make_db_user()
        await _invoke_scope_check(
            required_scopes=(ScopeType.ADMIN_WRITE, ScopeType.CHALLENGE_WRITE),
            jwt_payload={"sub": "uid-001"},
            db_user=user,
            role_scopes=[ScopeType.CHALLENGE_WRITE],
        )

    @pytest.mark.asyncio
    async def test_admin_with_all_scopes_passes_any_check(self):
        all_scopes = list(ScopeType)
        user = _make_db_user(role_id="role-admin-001")
        for scope in [ScopeType.CHALLENGE_WRITE, ScopeType.ADMIN_WRITE, ScopeType.SYSTEM_READ]:
            await _invoke_scope_check(
                required_scopes=(scope,),
                jwt_payload={"sub": "uid-admin"},
                db_user=user,
                role_scopes=all_scopes,
            )

    @pytest.mark.asyncio
    async def test_exact_scope_match_passes(self):
        """Scope value comparison must be exact — no partial matching."""
        user = _make_db_user()
        await _invoke_scope_check(
            required_scopes=(ScopeType.ROOM_WRITE,),
            jwt_payload={"sub": "uid-001"},
            db_user=user,
            role_scopes=[ScopeType.ROOM_WRITE],
        )


class TestRequireScopeForbidden:

    @pytest.mark.asyncio
    async def test_missing_scope_raises_403(self):
        user = _make_db_user()
        with pytest.raises(ScopeForbiddenException) as exc_info:
            await _invoke_scope_check(
                required_scopes=(ScopeType.ADMIN_WRITE,),
                jwt_payload={"sub": "uid-001"},
                db_user=user,
                role_scopes=[ScopeType.CHALLENGE_READ],
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_role_scopes_raises_403(self):
        user = _make_db_user()
        with pytest.raises(ScopeForbiddenException):
            await _invoke_scope_check(
                required_scopes=(ScopeType.CHALLENGE_READ,),
                jwt_payload={"sub": "uid-001"},
                db_user=user,
                role_scopes=[],
            )

    @pytest.mark.asyncio
    async def test_none_of_multiple_required_scopes_present_raises_403(self):
        """require_scope(A, B) — user has neither → should raise."""
        user = _make_db_user()
        with pytest.raises(ScopeForbiddenException):
            await _invoke_scope_check(
                required_scopes=(ScopeType.ADMIN_READ, ScopeType.ADMIN_WRITE),
                jwt_payload={"sub": "uid-001"},
                db_user=user,
                role_scopes=[ScopeType.CHALLENGE_READ, ScopeType.ROOM_READ],
            )

    @pytest.mark.asyncio
    async def test_similar_scope_prefix_does_not_match(self):
        """challenge:read must NOT grant challenge:write."""
        user = _make_db_user()
        with pytest.raises(ScopeForbiddenException):
            await _invoke_scope_check(
                required_scopes=(ScopeType.CHALLENGE_WRITE,),
                jwt_payload={"sub": "uid-001"},
                db_user=user,
                role_scopes=[ScopeType.CHALLENGE_READ],
            )

    @pytest.mark.asyncio
    async def test_read_scope_does_not_grant_write(self):
        """Symmetrical check — room:write must NOT satisfy room:read requirement... wait, that's wrong.
        Actually we're checking: having room:read does NOT let you perform room:write actions."""
        user = _make_db_user()
        with pytest.raises(ScopeForbiddenException):
            await _invoke_scope_check(
                required_scopes=(ScopeType.ROOM_WRITE,),
                jwt_payload={"sub": "uid-001"},
                db_user=user,
                role_scopes=[ScopeType.ROOM_READ],
            )


class TestRequireScopeUserNotFound:

    @pytest.mark.asyncio
    async def test_missing_db_user_raises_404(self):
        with pytest.raises(UserNotFoundException) as exc_info:
            await _invoke_scope_check(
                required_scopes=(ScopeType.CHALLENGE_READ,),
                jwt_payload={"sub": "uid-ghost"},
                db_user=None,  # DB lookup returns None
                role_scopes=[],
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_user_not_found_does_not_proceed_to_scope_check(self):
        """Role repo must never be queried if the user doesn't exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_user_id = AsyncMock(return_value=None)
        mock_role_repo = AsyncMock()

        inner = require_scope(ScopeType.CHALLENGE_READ)

        with patch("app.core.scope.dependencies.UserRepository", return_value=mock_user_repo), \
                patch("app.core.scope.dependencies.RoleRepository", return_value=mock_role_repo):
            with pytest.raises(UserNotFoundException):
                await inner(user={"sub": "uid-ghost"}, db=mock_db)

        mock_role_repo.get_user_scopes.assert_not_called()


class TestRequireScopeFactory:

    def test_factory_returns_callable(self):
        result = require_scope(ScopeType.CHALLENGE_READ)
        assert callable(result)

    def test_different_factories_are_independent(self):
        """Two require_scope calls with different scopes must produce different closures."""
        dep_a = require_scope(ScopeType.CHALLENGE_READ)
        dep_b = require_scope(ScopeType.ADMIN_WRITE)
        assert dep_a is not dep_b

    @pytest.mark.asyncio
    async def test_scope_check_uses_sub_from_jwt_payload(self):
        """The dependency must look up the user by payload['sub'], not by email or any other field."""
        mock_db = AsyncMock(spec=AsyncSession)
        user = _make_db_user(user_id="specific-uid-xyz")

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_user_id = AsyncMock(return_value=user)

        mock_role_repo = AsyncMock()
        mock_role_repo.get_user_scopes = AsyncMock(return_value=[ScopeType.CHALLENGE_READ])

        inner = require_scope(ScopeType.CHALLENGE_READ)

        with patch("app.core.scope.dependencies.UserRepository", return_value=mock_user_repo), \
                patch("app.core.scope.dependencies.RoleRepository", return_value=mock_role_repo):
            await inner(user={"sub": "specific-uid-xyz"}, db=mock_db)

        mock_user_repo.get_by_user_id.assert_called_once_with("specific-uid-xyz")

    @pytest.mark.asyncio
    async def test_role_repo_queried_with_users_role_id(self):
        """Scopes must be fetched using the user's actual role_id from the DB row."""
        mock_db = AsyncMock(spec=AsyncSession)
        role_id = "role-premium-999"
        user = _make_db_user(role_id=role_id)

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_user_id = AsyncMock(return_value=user)

        mock_role_repo = AsyncMock()
        mock_role_repo.get_user_scopes = AsyncMock(return_value=[ScopeType.CHALLENGE_READ])

        inner = require_scope(ScopeType.CHALLENGE_READ)

        with patch("app.core.scope.dependencies.UserRepository", return_value=mock_user_repo), \
                patch("app.core.scope.dependencies.RoleRepository", return_value=mock_role_repo):
            await inner(user={"sub": "uid-001"}, db=mock_db)

        mock_role_repo.get_user_scopes.assert_called_once_with(role_id)
