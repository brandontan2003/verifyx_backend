from app.dto.base import BaseDTO


class UserResponse(BaseDTO):
    user_id: str
    username: str
    xp: int
    streak: int


class LeaderboardResponse(BaseDTO):
    leaderboard: list[UserResponse]
