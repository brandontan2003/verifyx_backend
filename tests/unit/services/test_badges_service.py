from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import BadgeNotFoundException
from app.dto.progress import CreateBadgeRequest, UpdateBadgeRequest
from app.enums.BadgeEnum import BadgeType
from app.services.badges_service import (
    build_admin_badge_response,
    create_new_badge,
    retrieve_all_badges,
    update_badge,
)

DB = AsyncMock()


def _make_badge(badge_id="bdg-1", name="First Win", description="Won first challenge",
                badge_type=BadgeType.completion, threshold=1):
    b = MagicMock()
    b.badge_id = badge_id
    b.name = name
    b.description = description
    b.badge_type = badge_type
    b.threshold = threshold
    return b


def _make_progress_repo(badges=None, created=None, retrieved=None, updated=None):
    repo = MagicMock()
    repo.get_all_badges = AsyncMock(return_value=badges or [])
    repo.create_new_badge = AsyncMock(return_value=created or _make_badge())
    repo.retrieve_badge_by_badge_id = AsyncMock(return_value=retrieved)
    repo.update_badge = AsyncMock(return_value=updated or _make_badge())
    return repo


class TestBuildAdminBadgeResponse:
    @pytest.mark.asyncio
    async def test_maps_all_badge_fields(self):
        badges = [_make_badge("b1", "Streak 3", "3 days in a row", BadgeType.streak, 3)]
        result = await build_admin_badge_response(badges)

        assert len(result) == 1
        assert result[0].badge_id == "b1"
        assert result[0].name == "Streak 3"
        assert result[0].threshold == 3

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        result = await build_admin_badge_response([])
        assert result == []


class TestRetrieveAllBadges:
    @pytest.mark.asyncio
    async def test_returns_all_badges(self):
        badges = [_make_badge("b1"), _make_badge("b2")]
        repo = _make_progress_repo(badges=badges)

        with patch("app.services.badges_service.ProgressRepository", return_value=repo):
            result = await retrieve_all_badges(DB)

        assert len(result.badges) == 2

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self):
        repo = _make_progress_repo(badges=[])

        with patch("app.services.badges_service.ProgressRepository", return_value=repo):
            result = await retrieve_all_badges(DB)

        assert result.badges == []


class TestCreateNewBadge:
    @pytest.mark.asyncio
    async def test_creates_badge_and_returns_response(self):
        badge = _make_badge()
        repo = _make_progress_repo(created=badge)

        with patch("app.services.badges_service.ProgressRepository", return_value=repo):
            payload = CreateBadgeRequest(
                name="First Win", description="Win once",
                badge_type=BadgeType.completion, threshold=1
            )
            result = await create_new_badge(payload, DB)

        repo.create_new_badge.assert_awaited_once_with(
            "First Win", "Win once", BadgeType.completion, 1
        )
        assert result.badge_id == "bdg-1"

    @pytest.mark.asyncio
    async def test_returns_admin_badge_response(self):
        badge = _make_badge(badge_type=BadgeType.xp, threshold=100)
        repo = _make_progress_repo(created=badge)

        with patch("app.services.badges_service.ProgressRepository", return_value=repo):
            payload = CreateBadgeRequest(
                name="XP Hunter", description="Earn 100 XP",
                badge_type=BadgeType.xp, threshold=100
            )
            result = await create_new_badge(payload, DB)

        assert result.threshold == 100


class TestUpdateBadge:
    @pytest.mark.asyncio
    async def test_raises_badge_not_found(self):
        repo = _make_progress_repo(retrieved=None)

        with patch("app.services.badges_service.ProgressRepository", return_value=repo):
            with pytest.raises(BadgeNotFoundException):
                await update_badge("bdg-x", UpdateBadgeRequest(name="New", description="Desc"), DB)

    @pytest.mark.asyncio
    async def test_updates_and_returns_response(self):
        existing = _make_badge()
        updated = _make_badge(name="Updated", description="New desc")
        repo = _make_progress_repo(retrieved=existing, updated=updated)

        with patch("app.services.badges_service.ProgressRepository", return_value=repo):
            result = await update_badge("bdg-1", UpdateBadgeRequest(name="Updated", description="New desc"), DB)

        repo.update_badge.assert_awaited_once_with("bdg-1", "Updated", "New desc")
        assert result.name == "Updated"
