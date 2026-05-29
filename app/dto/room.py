from datetime import datetime
from typing import Optional

from app.dto.base import BaseDTO
from app.dto.challenge import ChallengeResponse
from app.enums.RoomStatusEnum import RoomStatus
from app.services.code_service import retrieve_theme


class CreateRoomRequest(BaseDTO):
    theme: str
    max_players: int = 8
    time_limit_seconds: int = 60

    @classmethod
    def __get_validators__(cls):
        yield cls.model_validate(CreateRoomRequest)

    def model_post_init(self, __context) -> None:
        theme_accepted = retrieve_theme()
        if not 2 <= self.max_players <= 20:
            raise ValueError("max_players must be 2-20")
        if self.time_limit_seconds < 15:
            raise ValueError("time_limit_seconds must be at least 15")
        if not self.theme.strip():
            raise ValueError("theme must not be blank")
        if self.theme.strip().lower() not in theme_accepted:
            raise ValueError(f"Invalid theme '{self.theme}'. Accepted values are: {', '.join(theme_accepted)}")
        self.theme = self.theme.strip().lower()


class JoinRoomRequest(BaseDTO):
    code: str

    def model_post_init(self, __context) -> None:
        self.code = self.code.strip().upper()
        if len(self.code) != 6:
            raise ValueError("room code must be 6 characters")


class ParticipantStatus(BaseDTO):
    user_id: str
    username: str
    is_correct: Optional[bool] = None
    xp_earned: Optional[int] = None
    time_taken_seconds: Optional[int] = None
    finished_at: Optional[datetime] = None


class RoomResponse(BaseDTO):
    room_id: str
    code: str
    host_user_id: str
    theme: str
    max_players: int
    time_limit_seconds: int
    status: RoomStatus
    participants: list[ParticipantStatus]
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class StartRoomResponse(BaseDTO):
    room_id: str
    status: RoomStatus
    challenge: ChallengeResponse


class LeaderboardEntry(BaseDTO):
    rank: int
    user_id: str
    username: str
    is_correct: bool
    xp_earned: int
    time_taken_seconds: int


class RoomLeaderboardResponse(BaseDTO):
    room_id: str
    theme: str
    entries: list[LeaderboardEntry]
