from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit.dependencies import read_rate_limit, room_rate_limit
from app.core.scope.dependencies import require_scope
from app.dependencies import get_current_user, get_db
from app.dto.base import DataResponse
from app.dto.challenge import ChallengeResponse
from app.dto.error import ErrorResponse
from app.dto.room import CreateRoomRequest, RoomResponse, StartRoomResponse, RoomLeaderboardResponse
from app.enums.ErrorEnum import ErrorEnum
from app.enums.ScopeEnum import ScopeType
from app.services.room_service import (
    create_room, join_room, start_room,
    get_room, get_my_challenge_in_room, get_leaderboard
)

router = APIRouter(prefix="/room", tags=["room"])


@router.post("", response_model=DataResponse[RoomResponse], summary="Create a multiplayer room (host auto-joins)",
             dependencies=[Depends(room_rate_limit), Depends(require_scope(ScopeType.ROOM_WRITE))],
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def create_room_endpoint(payload: CreateRoomRequest, user=Depends(get_current_user),
                               db: AsyncSession = Depends(get_db)):
    result = await create_room(user["sub"], payload, db)
    return DataResponse(result=result)


@router.post("/join", response_model=DataResponse[RoomResponse], summary="Join a room using its 6-character code",
             dependencies=[Depends(room_rate_limit), Depends(require_scope(ScopeType.ROOM_WRITE))],
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 404: {"model": ErrorResponse, "description": ErrorEnum.ROOM_NOT_FOUND.error_code},
                 409: {"model": ErrorResponse, "description": ErrorEnum.ROOM_FULL.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code},
             })
async def join_room_endpoint(code: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await join_room(user["sub"], code, db)
    return DataResponse(result=result)


@router.get("/{room_id}", response_model=DataResponse[RoomResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.ROOM_READ))],
            summary="Get current room state and participant list",
            responses={
                401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                404: {"model": ErrorResponse, "description": ErrorEnum.ROOM_NOT_FOUND.error_code}})
async def get_room_endpoint(room_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_room(user["sub"], room_id, db)
    return DataResponse(result=result)


@router.post("/{room_id}/start", response_model=DataResponse[StartRoomResponse],
             dependencies=[Depends(room_rate_limit), Depends(require_scope(ScopeType.ROOM_WRITE))],
             summary="Host only — generate shared scenario and start the round",
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 403: {"model": ErrorResponse, "description": ErrorEnum.NOT_ROOM_HOST.error_code},
                 404: {"model": ErrorResponse, "description": ErrorEnum.ROOM_NOT_FOUND.error_code},
                 409: {"model": ErrorResponse, "description": ErrorEnum.ROOM_ALREADY_ACTIVE.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}
             })
async def start_room_endpoint(room_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await start_room(user["sub"], room_id, db)
    return DataResponse(result=result)


@router.get("/{room_id}/challenge", response_model=DataResponse[ChallengeResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.ROOM_READ))],
            summary="Get this user's challenge for an active room",
            responses={
                401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                404: {"model": ErrorResponse, "description": ErrorEnum.ROOM_NOT_FOUND.error_code},
                409: {"model": ErrorResponse, "description": ErrorEnum.ROOM_NOT_ACTIVE.error_code},
                422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def get_room_challenge(room_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_my_challenge_in_room(user["sub"], room_id, db)
    return DataResponse(result=result)


@router.get("/{room_id}/leaderboard", response_model=DataResponse[RoomLeaderboardResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.ROOM_READ))],
            summary="Room results ranked by correctness then speed",
            responses={
                401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                404: {"model": ErrorResponse, "description": ErrorEnum.ROOM_NOT_FOUND.error_code},
                422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def get_room_leaderboard(room_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_leaderboard(room_id, db)
    return DataResponse(result=result)
