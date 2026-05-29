from app.dto.base import BaseDTO


class UpdateUsernameRequest(BaseDTO):
    username: str


class UserResponse(BaseDTO):
    user_id: str
    email: str
    username: str
    xp: int
    streak: int
