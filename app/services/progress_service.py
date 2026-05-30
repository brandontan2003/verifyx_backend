from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import UserNotFoundException
from app.core.logger import logger
from app.core.rules.scoring_engine import get_scoring_engine
from app.dto.progress import BadgeResponse, UpdateProgressResponse, UpdateProgressRequest, UserProgressResponse
from app.enums.BadgeEnum import BadgeType
from app.repositories.progress_repo import ProgressRepository
from app.repositories.user_repo import UserRepository


def calculate_xp(difficulty: int, time_taken: int, time_limit: int) -> int:
    return get_scoring_engine().calculate_xp(difficulty, time_taken, time_limit)


# Streak calculation
def calculate_new_streak(current_streak: int, last_activity_date: date | None, today: date) -> int:
    if last_activity_date is None:
        return 1

    delta = (today - last_activity_date).days

    if delta == 0:
        # already played today — no change
        return current_streak
    elif delta == 1:
        # consecutive day — increment
        return current_streak + 1
    else:
        # missed a day — reset
        return 1


# Badge checking
def get_badges_to_award(
        all_badges: list,
        earned_ids: set,
        streak: int,
        challenges_completed: int,
        total_xp: int = 0,
        perfect_scores: int = 0,
) -> list[str]:
    to_award = []

    perfect_badge_type = getattr(BadgeType, "perfect", None)

    for badge in all_badges:
        if badge.badge_id in earned_ids:
            continue

        if badge.badge_type == BadgeType.xp and total_xp >= badge.threshold:
            to_award.append(badge.badge_id)

        elif badge.badge_type == BadgeType.streak and streak >= badge.threshold:
            to_award.append(badge.badge_id)

        elif badge.badge_type == BadgeType.completion and challenges_completed >= badge.threshold:
            to_award.append(badge.badge_id)

        elif (
                perfect_badge_type is not None
                and badge.badge_type == perfect_badge_type
                and perfect_scores >= badge.threshold
        ):
            to_award.append(badge.badge_id)

    return to_award


# Main service methods
async def update_progress(user_id: str, payload: UpdateProgressRequest,
                          database: AsyncSession) -> UpdateProgressResponse:
    user_repo = UserRepository(database)
    progress_repo = ProgressRepository(database)

    user = await user_repo.get_by_user_id(user_id)
    if not user:
        raise UserNotFoundException()

    today = date.today()

    xp_earned = calculate_xp(
        payload.difficulty,
        payload.time_taken_seconds,
        payload.time_limit_seconds
    )

    new_streak = calculate_new_streak(
        user.streak,
        user.last_activity_date,
        today
    )

    updated_user = await progress_repo.update_progress(
        user_id=user_id,
        xp_earned=xp_earned,
        new_streak=new_streak,
        today=today,
        is_perfect=payload.is_perfect
    )

    # Check badge eligibility
    all_badges = await progress_repo.get_all_badges()
    earned_ids = await progress_repo.get_earned_badge_ids(user_id)

    to_award = get_badges_to_award(
        all_badges=all_badges,
        earned_ids=earned_ids,
        streak=updated_user.streak,
        challenges_completed=updated_user.challenges_completed,
        total_xp=updated_user.xp,
        perfect_scores=updated_user.perfect_scores
    )

    new_badges = []
    if to_award:
        new_badges = await progress_repo.award_badges(user_id, to_award)

    logger.info(
        "Progress updated for user %s: +%d XP, streak=%d, badges=%s",
        user_id,
        xp_earned,
        updated_user.streak,
        [b.badge_id for b in new_badges]
    )

    return UpdateProgressResponse(
        xp_earned=xp_earned,
        total_xp=updated_user.xp,
        streak=updated_user.streak,
        new_badges=await build_badge_response(new_badges)
    )


async def build_badge_response(badges: list) -> list[BadgeResponse]:
    return [
        BadgeResponse(
            badge_id=b.badge_id,
            name=b.name,
            description=b.description,
            badge_type=b.badge_type,
            threshold=b.threshold,
            earned_at=b.earned_at
        )
        for b in badges
    ]


async def get_user_progress(user_id: str, database: AsyncSession) -> UserProgressResponse:
    user_repo = UserRepository(database)
    progress_repo = ProgressRepository(database)

    user = await user_repo.get_by_user_id(user_id)
    if not user:
        raise UserNotFoundException()

    badges = await progress_repo.get_user_badges(user_id)

    return UserProgressResponse(
        total_xp=user.xp,
        streak=user.streak,
        challenges_completed=user.challenges_completed,
        perfect_scores=user.perfect_scores,
        badges=await build_badge_response(badges)
    )
