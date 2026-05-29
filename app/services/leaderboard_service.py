from app.dto.leaderboard import LeaderboardResponse, UserResponse
from app.repositories.user_repo import UserRepository


async def retrieve_leaderboard(database, limit) -> LeaderboardResponse:
    repo = UserRepository(database)
    users = await repo.get_leaderboard(limit)
    return LeaderboardResponse(
        leaderboard=[
            UserResponse(
                user_id=user.user_id,
                username=user.username,
                xp=user.xp,
                streak=user.streak,
            )
            for user in users
        ]
    )
