from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.leaderboard_service import retrieve_leaderboard

DB = AsyncMock()


class TestRetrieveLeaderboard:
    @pytest.mark.asyncio
    async def test_returns_ranked_users(self):
        u1 = MagicMock(user_id="u1", username="alice", xp=500, streak=5)
        u2 = MagicMock(user_id="u2", username="bob", xp=300, streak=2)
        repo = MagicMock()
        repo.get_leaderboard = AsyncMock(return_value=[u1, u2])

        with patch("app.services.leaderboard_service.UserRepository", return_value=repo):
            result = await retrieve_leaderboard(DB, limit=10)

        assert len(result.leaderboard) == 2
        assert result.leaderboard[0].username == "alice"
        assert result.leaderboard[0].xp == 500

    @pytest.mark.asyncio
    async def test_empty_leaderboard(self):
        repo = MagicMock()
        repo.get_leaderboard = AsyncMock(return_value=[])

        with patch("app.services.leaderboard_service.UserRepository", return_value=repo):
            result = await retrieve_leaderboard(DB, limit=10)

        assert result.leaderboard == []

    @pytest.mark.asyncio
    async def test_passes_limit_to_repo(self):
        repo = MagicMock()
        repo.get_leaderboard = AsyncMock(return_value=[])

        with patch("app.services.leaderboard_service.UserRepository", return_value=repo):
            await retrieve_leaderboard(DB, limit=5)

        repo.get_leaderboard.assert_awaited_once_with(5)
