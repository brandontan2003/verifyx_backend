"""
Room service — multiplayer session management.

Flow:
  1. Host calls create_room → gets room_id + 6-char code
  2. Players call join_room with the code
  3. Host calls start_room → Claude generates ONE scenario for the room,
     each participant gets their own Challenge row (same content, isolated answer)
  4. Each player calls the standard POST /challenge/{id}/submit endpoint
     (room_service.record_result is called from there via challenge_service)
  5. Anyone calls get_leaderboard once results are in
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import client as ai
from app.core.exceptions.exceptions import (
    RoomNotFoundException, RoomFullException, RoomAlreadyActiveException,
    NotRoomHostException, RoomNotActiveException
)
from app.core.logger import logger
from app.dto.challenge import ChallengeResponse, ChallengeOption
from app.dto.room import (
    CreateRoomRequest, RoomResponse, StartRoomResponse,
    ParticipantStatus, LeaderboardEntry, RoomLeaderboardResponse
)
from app.models.room import RoomStatus
from app.repositories.challenge_repo import ChallengeRepository
from app.repositories.room_repo import RoomRepository
from app.repositories.user_repo import UserRepository


def build_room_response(room, participants: list) -> RoomResponse:
    return RoomResponse(
        room_id=room.room_id,
        code=room.code,
        host_user_id=room.host_user_id,
        theme=room.theme,
        max_players=room.max_players,
        time_limit_seconds=room.time_limit_seconds,
        status=room.status,
        created_at=room.created_at,
        started_at=room.started_at,
        finished_at=room.finished_at,
        participants=[
            ParticipantStatus(
                user_id=p.user_id,
                username=p.username,
                is_correct=p.is_correct,
                xp_earned=p.xp_earned,
                time_taken_seconds=p.time_taken_seconds,
                finished_at=p.finished_at
            )
            for p in participants
        ]
    )


def _build_challenge_response(room, challenge_id: str) -> ChallengeResponse:
    """Build a ChallengeResponse from the shared room scenario — no correct_option_id."""
    scenario = room.scenario
    return ChallengeResponse(
        challenge_id=challenge_id,
        theme=room.theme,
        difficulty=scenario["difficulty"],
        title=scenario["title"],
        content=scenario["content"],
        question_type=scenario["question_type"],
        question=scenario["question"],
        options=[ChallengeOption(**o) for o in scenario["options"]],
        tags=scenario.get("tags"),
        room_id=room.room_id,
        created_at=room.started_at
    )


async def create_room(user_id: str, payload: CreateRoomRequest, database: AsyncSession) -> RoomResponse:
    room_repo = RoomRepository(database)
    room = await room_repo.create_room(
        host_user_id=user_id,
        theme=payload.theme,
        max_players=payload.max_players,
        time_limit_seconds=payload.time_limit_seconds
    )
    # Host auto-joins their own room
    user_repo = UserRepository(database)
    user = await user_repo.get_by_user_id(user_id)
    await room_repo.add_participant(room.room_id, user_id, user.username)

    participants = await room_repo.get_participants(room.room_id)
    logger.info("Room created: %s (code=%s) by user %s", room.room_id, room.code, user_id)
    return build_room_response(room, participants)


async def join_room(user_id: str, code: str, database: AsyncSession) -> RoomResponse:
    room_repo = RoomRepository(database)
    user_repo = UserRepository(database)

    room = await room_repo.get_by_code(code)
    if not room:
        raise RoomNotFoundException()
    if room.status != RoomStatus.waiting:
        raise RoomAlreadyActiveException()

    # Idempotent — if already in room, just return current state
    existing = await room_repo.get_participant(room.room_id, user_id)
    if existing:
        participants = await room_repo.get_participants(room.room_id)
        return build_room_response(room, participants)

    count = await room_repo.participant_count(room.room_id)
    if count >= room.max_players:
        raise RoomFullException()

    user = await user_repo.get_by_user_id(user_id)
    await room_repo.add_participant(room.room_id, user_id, user.username)

    participants = await room_repo.get_participants(room.room_id)
    logger.info("User %s joined room %s", user_id, room.room_id)
    return build_room_response(room, participants)


async def start_room(user_id: str, room_id: str, database: AsyncSession) -> StartRoomResponse:
    """
    Host-only. Generates ONE scenario via Claude, persists it on the room,
    then creates an individual Challenge row for every participant.
    """
    room_repo = RoomRepository(database)
    challenge_repo = ChallengeRepository(database)

    room = await room_repo.get_room(room_id)
    if not room:
        raise RoomNotFoundException()
    if room.host_user_id != user_id:
        raise NotRoomHostException()
    if room.status != RoomStatus.waiting:
        raise RoomAlreadyActiveException()

    # Claude generates the shared scenario
    scenario = await ai.generate_scenario(
        theme=room.theme,
        attempt_count=0,
        user_history=[]
    )

    room = await room_repo.start_room(room_id, scenario)
    participants = await room_repo.get_participants(room_id)

    # Create one Challenge row per participant (same content, separate rows)
    for p in participants:
        challenge = await challenge_repo.create_challenge(
            user_id=p.user_id,
            theme=scenario["theme"],
            difficulty=scenario["difficulty"],
            title=scenario["title"],
            content=scenario["content"],
            question_type=scenario["question_type"],
            question=scenario["question"],
            options=scenario["options"],
            correct_option_id=scenario["correct_option_id"],
            tags=scenario.get("tags"),
            room_id=room_id
        )
        await room_repo.set_participant_challenge(room_id, p.user_id, challenge.challenge_id)

    # Return the challenge for the requesting user
    host_participant = await room_repo.get_participant(room_id, user_id)
    challenge_response = _build_challenge_response(room, host_participant.challenge_id)

    logger.info("Room %s started — %d participants", room_id, len(participants))
    return StartRoomResponse(room_id=room_id, status=room.status, challenge=challenge_response)


async def get_room(user_id: str, room_id: str, database: AsyncSession) -> RoomResponse:
    room_repo = RoomRepository(database)
    room = await room_repo.get_room(room_id)
    if not room:
        raise RoomNotFoundException()

    # If user is a participant and room is active, include their challenge_id
    # so the frontend knows which challenge to load
    participants = await room_repo.get_participants(room_id)
    return build_room_response(room, participants)


async def get_my_challenge_in_room(user_id: str, room_id: str, database: AsyncSession) -> ChallengeResponse:
    """Return this user's challenge for an active room."""
    room_repo = RoomRepository(database)
    room = await room_repo.get_room(room_id)
    if not room:
        raise RoomNotFoundException()
    if room.status == RoomStatus.waiting:
        raise RoomNotActiveException()

    participant = await room_repo.get_participant(room_id, user_id)
    if not participant or not participant.challenge_id:
        raise RoomNotFoundException()  # user not in this room

    return _build_challenge_response(room, participant.challenge_id)


async def record_room_result(
        room_id: str,
        user_id: str,
        is_correct: bool,
        xp_earned: int,
        time_taken_seconds: int,
        database: AsyncSession
) -> None:
    """
    Called internally by challenge_service.submit_answer when the challenge
    belongs to a room. Updates participant record and auto-closes room if done.
    """
    room_repo = RoomRepository(database)
    await room_repo.record_participant_result(room_id, user_id, is_correct, xp_earned, time_taken_seconds)
    finished = await room_repo.finish_room_if_all_done(room_id)
    if finished:
        logger.info("Room %s finished — all participants submitted", room_id)


async def get_leaderboard(room_id: str, database: AsyncSession) -> RoomLeaderboardResponse:
    room_repo = RoomRepository(database)
    room = await room_repo.get_room(room_id)
    if not room:
        raise RoomNotFoundException()

    participants = await room_repo.get_participants(room_id)

    # Only rank participants who have submitted
    submitted = [p for p in participants if p.is_correct is not None]

    # Sort: correct first, then by time ascending
    submitted.sort(key=lambda p: (not p.is_correct, p.time_taken_seconds or 99999))

    entries = [
        LeaderboardEntry(
            rank=i + 1,
            user_id=p.user_id,
            username=p.username,
            is_correct=p.is_correct,
            xp_earned=p.xp_earned or 0,
            time_taken_seconds=p.time_taken_seconds or 0
        )
        for i, p in enumerate(submitted)
    ]
    return RoomLeaderboardResponse(
        room_id=room_id,
        theme=room.theme,
        entries=entries
    )
