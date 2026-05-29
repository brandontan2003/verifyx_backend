from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.RoleEnum import RoleType
from app.models.role import Role
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_leaderboard(self, limit: int) -> list[User]:
        result = await self.db.execute(select(User).order_by(User.xp.desc()).limit(limit))
        return list(result.scalars().all())

    async def get_by_email(self, email_address: str) -> User:
        result = await self.db.execute(select(User).where(User.email == email_address))
        user = result.scalar_one_or_none()
        if user:
            await self.db.refresh(user)
        return user

    async def get_by_user_id(self, user_id: str) -> User:
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if user:
            await self.db.refresh(user)
        return user

    async def create(self, user_id: str, email: str, username: str) -> User:
        result = await self.db.execute(select(Role.role_id).where(Role.name == RoleType.USER))
        role_id = result.scalar_one_or_none()
        user = User(user_id=user_id, email=email, username=username, role_id=role_id)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_username(self, user_id: str, username: str) -> User:
        result = await self.db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.username = username
            await self.db.commit()
            await self.db.refresh(user)
        return user
