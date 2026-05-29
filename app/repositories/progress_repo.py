from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import UserNotFoundException
from app.enums.BadgeEnum import BadgeType
from app.models.badge import Badges, UserBadges
from app.models.user import User


class ProgressRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_progress(self, user_id: str, xp_earned: int, new_streak: int, today: date,
                              is_perfect: bool) -> User:
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundException()

        user.xp += xp_earned
        user.streak = new_streak
        user.challenges_completed += 1
        user.last_activity_date = today

        if is_perfect:
            user.perfect_scores += 1

        await self.db.commit()
        await self.db.refresh(user)
        return user

    # Badge-related methods
    async def get_all_badges(self) -> list[Badges]:
        result = await self.db.execute(select(Badges))
        return list(result.scalars().all())

    async def get_earned_badge_ids(self, user_id: str) -> set[str]:
        result = await self.db.execute(
            select(UserBadges.badge_id).where(UserBadges.user_id == user_id)
        )
        return set(result.scalars().all())

    async def award_badges(self, user_id: str, badge_ids: list[str]):
        # Create UserBadges entries for each new badge
        for badge_id in badge_ids:
            user_badge = UserBadges(user_id=user_id, badge_id=badge_id)
            self.db.add(user_badge)
        await self.db.commit()

        # Fetch and return the awarded badges
        result = await self.db.execute(
            select(
                Badges.badge_id,
                Badges.name,
                Badges.description,
                Badges.badge_type,
                Badges.threshold,
                UserBadges.earned_at
            )
            .join(UserBadges, UserBadges.badge_id == Badges.badge_id)
            .where(
                UserBadges.user_id == user_id,
                UserBadges.badge_id.in_(badge_ids)
            )
        )
        return list(result.all())

    async def get_user_badges(self, user_id: str):
        result = await self.db.execute(
            select(
                Badges.badge_id,
                Badges.name,
                Badges.description,
                Badges.badge_type,
                Badges.threshold,
                UserBadges.earned_at
            )
            .join(UserBadges, UserBadges.badge_id == Badges.badge_id)
            .where(UserBadges.user_id == user_id)
        )
        return list(result.all())

    async def create_new_badge(self, badge_name: str, description: str, badge_type: str, threshold: int):
        new_badge = Badges(
            name=badge_name,
            description=description,
            badge_type=BadgeType(badge_type),
            threshold=threshold
        )

        self.db.add(new_badge)
        await self.db.commit()
        await self.db.refresh(new_badge)
        return new_badge

    async def retrieve_badge_by_badge_id(self, badge_id: str):
        result = await self.db.execute(select(Badges).where(Badges.badge_id == badge_id))
        return result.scalar_one_or_none()

    async def update_badge(self, badge_id: str, badge_name: str, description: str):
        badge = await self.retrieve_badge_by_badge_id(badge_id)

        if badge:
            if badge_name is not None:
                badge.name = badge_name
            if description is not None:
                badge.description = description
            await self.db.commit()
            await self.db.refresh(badge)
        return badge
