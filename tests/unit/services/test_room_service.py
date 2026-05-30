"""
Unit tests for app/services/room_service.py

Covers:
  - build_room_response
  - _build_challenge_response
  - create_room
  - join_room
  - start_room
  - get_room
  - get_my_challenge_in_room
  - record_room_result
  - get_leaderboard
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import (
    NotRoomHostException,
    RoomAlreadyActiveException,
    RoomFullException,
    RoomNotFoundException,
    RoomNotActiveException,
)
from app.dto.room import CreateRoomRequest
from app.models.room import RoomStatus
from app.services.room_service import (
    _build_challenge_response,
    build_room_response,
    create_room,
    get_leaderboard,
    get_my_challenge_in_room,
    get_room,
    join_room,
    record_room_result,
    start_room,
)

DB = AsyncMock()


def _make_room(room_id="room-1", code="ABC123", host_user_id="user-1", theme="scam", max_players=4,
               time_limit_seconds=60, status=RoomStatus.waiting, scenario=None):
    r = MagicMock()
    r.room_id = room_id
    r.code = code
    r.host_user_id = host_user_id
    r.theme = theme
    r.max_players = max_players
    r.time_limit_seconds = time_limit_seconds
    r.status = status
    r.created_at = datetime(2024, 1, 1)
    r.started_at = None
    r.finished_at = None
    r.scenario = scenario or {
        "difficulty": 2,
        "title": "Room Challenge",
        "content": "Someone sent you a suspicious link.",
        "question_type": "mcq",
        "question": "Is this a scam?",
        "options": [{"id": "A", "text": "Yes"}, {"id": "B", "text": "No"},
                    {"id": "C", "text": "Maybe"}, {"id": "D", "text": "Unsure"}],
        "correct_option_id": "A",
        "tags": ["scam"],
    }
    return r


def _make_participant(user_id="user-1", username="alice", challenge_id="ch-1",
                      is_correct=None, xp_earned=None, time_taken_seconds=None,
                      finished_at=None):
    p = MagicMock()
    p.user_id = user_id
    p.username = username
    p.challenge_id = challenge_id
    p.is_correct = is_correct
    p.xp_earned = xp_earned
    p.time_taken_seconds = time_taken_seconds
    p.finished_at = finished_at
    return p


def _make_user(user_id="user-1", username="alice"):
    u = MagicMock()
    u.user_id = user_id
    u.username = username
    return u


def _make_challenge(challenge_id="ch-1"):
    c = MagicMock()
    c.challenge_id = challenge_id
    return c


def _room_repo(room=None, participants=None, participant=None, count=0, created_room=None, started_room=None,
               finished=False, get_by_code_result=None):
    repo = MagicMock()
    repo.get_room = AsyncMock(return_value=room)
    repo.get_by_code = AsyncMock(return_value=get_by_code_result or room)
    repo.get_participants = AsyncMock(return_value=participants or [])
    repo.get_participant = AsyncMock(return_value=participant)
    repo.participant_count = AsyncMock(return_value=count)
    repo.add_participant = AsyncMock(return_value=None)
    repo.create_room = AsyncMock(return_value=created_room or room)
    repo.start_room = AsyncMock(return_value=started_room or room)
    repo.set_participant_challenge = AsyncMock(return_value=None)
    repo.record_participant_result = AsyncMock(return_value=None)
    repo.finish_room_if_all_done = AsyncMock(return_value=finished)
    return repo


def _challenge_repo(challenge=None):
    repo = MagicMock()
    repo.create_challenge = AsyncMock(return_value=challenge or _make_challenge())
    return repo


def _user_repo(user=None):
    repo = MagicMock()
    repo.get_by_user_id = AsyncMock(return_value=user or _make_user())
    return repo


class TestBuildRoomResponse:
    def test_maps_room_fields(self):
        room = _make_room()
        p = _make_participant()
        result = build_room_response(room, [p])

        assert result.room_id == "room-1"
        assert result.code == "ABC123"
        assert result.host_user_id == "user-1"
        assert result.theme == "scam"
        assert len(result.participants) == 1
        assert result.participants[0].user_id == "user-1"
        assert result.participants[0].username == "alice"

    def test_empty_participants(self):
        room = _make_room()
        result = build_room_response(room, [])
        assert result.participants == []

    def test_multiple_participants(self):
        room = _make_room()
        ps = [_make_participant("u1", "alice"), _make_participant("u2", "bob")]
        result = build_room_response(room, ps)
        assert len(result.participants) == 2
        assert result.participants[1].username == "bob"


class TestBuildChallengeResponse:
    def test_builds_from_room_scenario(self):
        room = _make_room(status=RoomStatus.active)
        room.started_at = datetime(2024, 6, 1)
        result = _build_challenge_response(room, "ch-xyz")

        assert result.challenge_id == "ch-xyz"
        assert result.room_id == "room-1"
        assert result.theme == "scam"
        assert result.title == "Room Challenge"
        assert len(result.options) == 4
        assert result.created_at == datetime(2024, 6, 1)

    def test_correct_option_id_not_in_challenge_response_fields(self):
        """ChallengeResponse intentionally excludes correct_option_id."""
        room = _make_room()
        room.started_at = datetime(2024, 6, 1)
        result = _build_challenge_response(room, "ch-xyz")
        # ChallengeResponse schema has no correct_option_id field
        assert "correct_option_id" not in result.options


class TestCreateRoom:
    @pytest.mark.asyncio
    async def test_creates_room_and_host_joins(self):
        room = _make_room()
        rr = _room_repo(room=room, created_room=room, participants=[_make_participant()])
        ur = _user_repo()
        cr = _challenge_repo()

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=ur):
            payload = CreateRoomRequest(theme="scam", max_players=4, time_limit_seconds=60)
            result = await create_room("user-1", payload, DB)

        rr.create_room.assert_awaited_once()
        rr.add_participant.assert_awaited_once_with("room-1", "user-1", "alice")
        assert result.room_id == "room-1"

    @pytest.mark.asyncio
    async def test_returns_room_response_with_host_participant(self):
        room = _make_room()
        p = _make_participant()
        rr = _room_repo(room=room, created_room=room, participants=[p])
        ur = _user_repo()

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=ur):
            payload = CreateRoomRequest(theme="scam", max_players=4, time_limit_seconds=60)
            result = await create_room("user-1", payload, DB)

        assert len(result.participants) == 1


class TestJoinRoom:
    @pytest.mark.asyncio
    async def test_raises_room_not_found_when_code_invalid(self):
        rr = _room_repo(get_by_code_result=None)
        rr.get_by_code = AsyncMock(return_value=None)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=_user_repo()):
            with pytest.raises(RoomNotFoundException):
                await join_room("user-2", "BADCODE", DB)

    @pytest.mark.asyncio
    async def test_raises_already_active_when_room_not_waiting(self):
        room = _make_room(status=RoomStatus.active)
        rr = _room_repo(room=room)
        rr.get_by_code = AsyncMock(return_value=room)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=_user_repo()):
            with pytest.raises(RoomAlreadyActiveException):
                await join_room("user-2", "ABC123", DB)

    @pytest.mark.asyncio
    async def test_idempotent_if_already_in_room(self):
        room = _make_room()
        p = _make_participant()
        rr = _room_repo(room=room, participant=p, participants=[p])
        rr.get_by_code = AsyncMock(return_value=room)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=_user_repo()):
            result = await join_room("user-1", "ABC123", DB)

        rr.add_participant.assert_not_awaited()
        assert result.room_id == "room-1"

    @pytest.mark.asyncio
    async def test_raises_room_full_when_at_capacity(self):
        room = _make_room(max_players=2)
        rr = _room_repo(room=room, participant=None, count=2)
        rr.get_by_code = AsyncMock(return_value=room)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=_user_repo()):
            with pytest.raises(RoomFullException):
                await join_room("user-3", "ABC123", DB)

    @pytest.mark.asyncio
    async def test_adds_new_participant_when_room_has_space(self):
        room = _make_room(max_players=4)
        p = _make_participant("user-2", "bob")
        rr = _room_repo(room=room, participant=None, count=1, participants=[p])
        rr.get_by_code = AsyncMock(return_value=room)
        ur = _user_repo(_make_user("user-2", "bob"))

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.UserRepository", return_value=ur):
            result = await join_room("user-2", "ABC123", DB)

        rr.add_participant.assert_awaited_once_with("room-1", "user-2", "bob")
        assert result.room_id == "room-1"


class TestStartRoom:
    @pytest.mark.asyncio
    async def test_raises_room_not_found(self):
        rr = _room_repo(room=None)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.ChallengeRepository", return_value=_challenge_repo()):
            with pytest.raises(RoomNotFoundException):
                await start_room("user-1", "room-1", DB)

    @pytest.mark.asyncio
    async def test_raises_not_host(self):
        room = _make_room(host_user_id="user-1")
        rr = _room_repo(room=room)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.ChallengeRepository", return_value=_challenge_repo()):
            with pytest.raises(NotRoomHostException):
                await start_room("user-2", "room-1", DB)

    @pytest.mark.asyncio
    async def test_raises_already_active(self):
        room = _make_room(host_user_id="user-1", status=RoomStatus.active)
        rr = _room_repo(room=room)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.ChallengeRepository", return_value=_challenge_repo()):
            with pytest.raises(RoomAlreadyActiveException):
                await start_room("user-1", "room-1", DB)

    @pytest.mark.asyncio
    async def test_creates_challenge_per_participant(self):
        scenario = {
            "theme": "scam",
            "difficulty": 2,
            "title": "Room Challenge",
            "content": "Someone sent you a suspicious link.",
            "question_type": "mcq",
            "question": "Is this a scam?",
            "options": [{"id": "A", "text": "Yes"}, {"id": "B", "text": "No"},
                        {"id": "C", "text": "Maybe"}, {"id": "D", "text": "Unsure"}],
            "correct_option_id": "A",
            "tags": ["scam"],
        }
        room = _make_room(host_user_id="user-1", status=RoomStatus.waiting)
        started_room = _make_room(host_user_id="user-1", status=RoomStatus.active)
        started_room.started_at = datetime(2024, 6, 1)
        started_room.scenario = scenario

        p1 = _make_participant("user-1", "alice", "ch-1")
        p2 = _make_participant("user-2", "bob", "ch-2")
        participants = [p1, p2]

        rr = _room_repo(room=room, participants=participants, participant=p1, started_room=started_room)
        cr = _challenge_repo()

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.ChallengeRepository", return_value=cr), \
                patch("app.services.room_service.ai.generate_scenario", AsyncMock(return_value=scenario)):
            result = await start_room("user-1", "room-1", DB)

        assert cr.create_challenge.await_count == 2
        assert result.room_id == "room-1"

    @pytest.mark.asyncio
    async def test_returns_host_challenge_in_response(self):
        scenario = {
            "theme": "scam",
            "difficulty": 2,
            "title": "Room Challenge",
            "content": "Someone sent you a suspicious link.",
            "question_type": "mcq",
            "question": "Is this a scam?",
            "options": [{"id": "A", "text": "Yes"}, {"id": "B", "text": "No"},
                        {"id": "C", "text": "Maybe"}, {"id": "D", "text": "Unsure"}],
            "correct_option_id": "A",
            "tags": ["scam"],
        }
        room = _make_room(host_user_id="user-1", status=RoomStatus.waiting)
        started_room = _make_room(host_user_id="user-1", status=RoomStatus.active)
        started_room.started_at = datetime(2024, 6, 1)
        started_room.scenario = scenario

        host_p = _make_participant("user-1", "alice", "ch-host")
        rr = _room_repo(room=room, participants=[host_p], participant=host_p, started_room=started_room)
        cr = _challenge_repo()

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.ChallengeRepository", return_value=cr), \
                patch("app.services.room_service.ai.generate_scenario", AsyncMock(return_value=scenario)):
            result = await start_room("user-1", "room-1", DB)

        assert result.challenge.challenge_id == "ch-host"


class TestGetRoom:
    @pytest.mark.asyncio
    async def test_raises_room_not_found(self):
        rr = _room_repo(room=None)
        with patch("app.services.room_service.RoomRepository", return_value=rr):
            with pytest.raises(RoomNotFoundException):
                await get_room("user-1", "room-1", DB)

    @pytest.mark.asyncio
    async def test_returns_room_with_participants(self):
        room = _make_room()
        ps = [_make_participant()]
        rr = _room_repo(room=room, participants=ps)

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_room("user-1", "room-1", DB)

        assert result.room_id == "room-1"
        assert len(result.participants) == 1


class TestGetMyChallengeInRoom:
    @pytest.mark.asyncio
    async def test_raises_room_not_found_when_missing(self):
        rr = _room_repo(room=None)
        with patch("app.services.room_service.RoomRepository", return_value=rr):
            with pytest.raises(RoomNotFoundException):
                await get_my_challenge_in_room("user-1", "room-1", DB)

    @pytest.mark.asyncio
    async def test_raises_room_not_active_when_waiting(self):
        room = _make_room(status=RoomStatus.waiting)
        rr = _room_repo(room=room)
        with patch("app.services.room_service.RoomRepository", return_value=rr):
            with pytest.raises(RoomNotActiveException):
                await get_my_challenge_in_room("user-1", "room-1", DB)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_user_not_participant(self):
        room = _make_room(status=RoomStatus.active)
        rr = _room_repo(room=room, participant=None)
        with patch("app.services.room_service.RoomRepository", return_value=rr):
            with pytest.raises(RoomNotFoundException):
                await get_my_challenge_in_room("user-9", "room-1", DB)

    @pytest.mark.asyncio
    async def test_returns_challenge_response_for_participant(self):
        room = _make_room(status=RoomStatus.active)
        room.started_at = datetime(2024, 6, 1)
        p = _make_participant("user-1", "alice", "ch-42")
        rr = _room_repo(room=room, participant=p)

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_my_challenge_in_room("user-1", "room-1", DB)

        assert result.challenge_id == "ch-42"
        assert result.room_id == "room-1"


class TestRecordRoomResult:
    @pytest.mark.asyncio
    async def test_records_result_and_checks_finish(self):
        rr = _room_repo(finished=False)

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            await record_room_result("room-1", "user-1", True, 50, 30, DB)

        rr.record_participant_result.assert_awaited_once_with("room-1", "user-1", True, 50, 30)
        rr.finish_room_if_all_done.assert_awaited_once_with("room-1")

    @pytest.mark.asyncio
    async def test_logs_when_room_finishes(self):
        rr = _room_repo(finished=True)

        with patch("app.services.room_service.RoomRepository", return_value=rr), \
                patch("app.services.room_service.logger") as mock_logger:
            await record_room_result("room-1", "user-1", True, 50, 30, DB)

        mock_logger.info.assert_called()


class TestGetLeaderboard:
    @pytest.mark.asyncio
    async def test_raises_room_not_found(self):
        rr = _room_repo(room=None)
        with patch("app.services.room_service.RoomRepository", return_value=rr):
            with pytest.raises(RoomNotFoundException):
                await get_leaderboard("room-1", DB)

    @pytest.mark.asyncio
    async def test_excludes_unsubmitted_participants(self):
        room = _make_room()
        p_done = _make_participant("u1", "alice", is_correct=True, xp_earned=50, time_taken_seconds=20)
        p_pending = _make_participant("u2", "bob", is_correct=None)
        rr = _room_repo(room=room, participants=[p_done, p_pending])

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_leaderboard("room-1", DB)

        assert len(result.entries) == 1
        assert result.entries[0].user_id == "u1"

    @pytest.mark.asyncio
    async def test_correct_answers_rank_higher_than_wrong(self):
        room = _make_room()
        p_wrong = _make_participant("u1", "alice", is_correct=False, xp_earned=0, time_taken_seconds=10)
        p_correct = _make_participant("u2", "bob", is_correct=True, xp_earned=50, time_taken_seconds=40)
        rr = _room_repo(room=room, participants=[p_wrong, p_correct])

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_leaderboard("room-1", DB)

        assert result.entries[0].user_id == "u2"  # correct first
        assert result.entries[1].user_id == "u1"

    @pytest.mark.asyncio
    async def test_same_correctness_sorted_by_time_ascending(self):
        room = _make_room()
        fast = _make_participant("u1", "alice", is_correct=True, xp_earned=80, time_taken_seconds=10)
        slow = _make_participant("u2", "bob", is_correct=True, xp_earned=50, time_taken_seconds=55)
        rr = _room_repo(room=room, participants=[slow, fast])

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_leaderboard("room-1", DB)

        assert result.entries[0].user_id == "u1"  # fastest first

    @pytest.mark.asyncio
    async def test_returns_room_theme(self):
        room = _make_room(theme="phishing")
        p = _make_participant("u1", "alice", is_correct=True, xp_earned=40, time_taken_seconds=20)
        rr = _room_repo(room=room, participants=[p])

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_leaderboard("room-1", DB)

        assert result.theme == "phishing"

    @pytest.mark.asyncio
    async def test_assigns_sequential_ranks(self):
        room = _make_room()
        ps = [
            _make_participant("u1", "a", is_correct=True, xp_earned=80, time_taken_seconds=5),
            _make_participant("u2", "b", is_correct=True, xp_earned=50, time_taken_seconds=20),
            _make_participant("u3", "c", is_correct=False, xp_earned=0, time_taken_seconds=60),
        ]
        rr = _room_repo(room=room, participants=ps)

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_leaderboard("room-1", DB)

        assert [e.rank for e in result.entries] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_empty_leaderboard_when_no_submissions(self):
        room = _make_room()
        ps = [_make_participant("u1", "a", is_correct=None)]
        rr = _room_repo(room=room, participants=ps)

        with patch("app.services.room_service.RoomRepository", return_value=rr):
            result = await get_leaderboard("room-1", DB)

        assert result.entries == []
