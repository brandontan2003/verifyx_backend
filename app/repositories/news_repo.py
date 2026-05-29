from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.NewsEnum import ReactionType
from app.models.news import NewsPost, Comment, NewsReaction


class NewsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_news_post(self, report_id: str, title: str, harm_type: str, content: str,
                               context: Optional[str]) -> NewsPost:
        post = NewsPost(
            news_id=str(uuid4()),
            report_id=report_id,
            title=title,
            harm_type=harm_type,
            content=content,
            context=context,
            upvotes=0,
            downvotes=0,
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def get_by_news_id(self, news_id: str) -> Optional[NewsPost]:
        result = await self.db.execute(
            select(NewsPost).where(NewsPost.news_id == news_id)
        )
        return result.scalar_one_or_none()

    async def get_by_report_id(self, report_id: str) -> Optional[NewsPost]:
        result = await self.db.execute(
            select(NewsPost).where(NewsPost.report_id == report_id)
        )
        return result.scalar_one_or_none()

    async def list_posts(self, page: int, page_size: int) -> tuple[list[NewsPost], int]:
        base = select(NewsPost)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        data_result = await self.db.execute(
            base.order_by(NewsPost.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(data_result.scalars().all()), total

    async def increment_upvotes(self, news_id: str) -> None:
        await self.db.execute(
            update(NewsPost)
            .where(NewsPost.news_id == news_id)
            .values(upvotes=NewsPost.upvotes + 1)
        )
        await self.db.commit()

    async def decrement_upvotes(self, news_id: str) -> None:
        await self.db.execute(
            update(NewsPost)
            .where(NewsPost.news_id == news_id)
            .values(upvotes=func.greatest(0, NewsPost.upvotes - 1))
        )
        await self.db.commit()

    async def increment_downvotes(self, news_id: str) -> None:
        await self.db.execute(
            update(NewsPost)
            .where(NewsPost.news_id == news_id)
            .values(downvotes=NewsPost.downvotes + 1)
        )
        await self.db.commit()

    async def decrement_downvotes(self, news_id: str) -> None:
        await self.db.execute(
            update(NewsPost)
            .where(NewsPost.news_id == news_id)
            .values(downvotes=func.greatest(0, NewsPost.downvotes - 1))
        )
        await self.db.commit()

    async def create_comment(self, news_id: str, user_id: str, body: str, parent_id: Optional[str],
                             depth: int) -> Comment:
        comment = Comment(
            comment_id=str(uuid4()),
            news_id=news_id,
            user_id=user_id,
            body=body,
            parent_id=parent_id,
            depth=depth,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def get_comment_by_id(self, comment_id: str) -> Optional[Comment]:
        result = await self.db.execute(
            select(Comment).where(Comment.comment_id == comment_id)
        )
        return result.scalar_one_or_none()

    async def get_comments_for_post(self, news_id: str) -> list[Comment]:
        """Return all comments for a post ordered oldest-first for thread assembly."""
        result = await self.db.execute(
            select(Comment)
            .where(Comment.news_id == news_id)
            .order_by(Comment.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_comments_for_post(self, news_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(Comment.news_id == news_id)
        )
        return result.scalar_one()

    async def get_reaction(self, news_id: str, user_id: str) -> Optional[NewsReaction]:
        result = await self.db.execute(
            select(NewsReaction)
            .where(NewsReaction.news_id == news_id)
            .where(NewsReaction.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_reaction(self, news_id: str, user_id: str,
                              reaction_type: ReactionType) -> tuple[Optional[ReactionType], ReactionType]:
        """
        Returns (previous_reaction_type, new_reaction_type).
        Handles: new react, switch react, same react (no-op toggle not needed per spec).
        """
        existing = await self.get_reaction(news_id, user_id)
        previous = ReactionType(existing.reaction_type) if existing else None

        if existing is None:
            reaction = NewsReaction(
                reaction_id=str(uuid4()),
                news_id=news_id,
                user_id=user_id,
                reaction_type=reaction_type,
            )
            self.db.add(reaction)
        else:
            existing.reaction_type = reaction_type

        await self.db.commit()
        return previous, reaction_type
