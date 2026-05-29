from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import (
    NewsPostNotFoundException,
    CommentNotFoundException,
    CommentDepthExceededException,
)
from app.core.logger import logger
from app.dto.news import (
    NewsFeedResponse,
    NewsPostDetail,
    NewsPostSummary,
    CommentResponse,
    CreateCommentRequest,
    ReactRequest,
)
from app.enums.NewsEnum import ReactionType
from app.models.news import NewsPost, Comment
from app.repositories.news_repo import NewsRepository
from app.repositories.user_repo import UserRepository

MAX_COMMENT_DEPTH = 1  # 0 = top-level, 1 = reply — no deeper


# ── Auto-publish ──────────────────────────────────────────────────────────────

def _build_title(harm_type: str, content: str) -> str:
    """Template: '[Harm Type] Alert: [first 60 chars of content]'"""
    label = harm_type.replace("_", " ").title()
    preview = content.strip()[:60]
    if len(content.strip()) > 60:
        preview += "…"
    return f"{label} Alert: {preview}"


async def auto_publish_news_post(report_id: str, harm_type: str, content: str, context: Optional[str],
                                 database: AsyncSession, ) -> NewsPost:
    """
    Called by report_service when a report transitions to APPROVED.
    Idempotent — if a news post already exists for this report, returns it.
    """
    repo = NewsRepository(database)

    existing = await repo.get_by_report_id(report_id)
    if existing:
        logger.info("News post already exists for report %s, skipping", report_id)
        return existing

    title = _build_title(harm_type, content)
    post = await repo.create_news_post(
        report_id=report_id,
        title=title,
        harm_type=harm_type,
        content=content,
        context=context,
    )
    logger.info("Auto-published news post %s from report %s", post.news_id, report_id)
    return post


async def get_news_feed(page: int, page_size: int, database: AsyncSession) -> NewsFeedResponse:
    repo = NewsRepository(database)
    posts, total = await repo.list_posts(page, page_size)

    summaries = []
    for p in posts:
        comment_count = await repo.count_comments_for_post(p.news_id)
        summaries.append(
            NewsPostSummary(
                news_id=p.news_id,
                report_id=p.report_id,
                title=p.title,
                harm_type=p.harm_type,
                content=p.content[:200] + "…" if len(p.content) > 200 else p.content,
                upvotes=p.upvotes,
                downvotes=p.downvotes,
                comment_count=comment_count,
                created_at=p.created_at,
            )
        )

    return NewsFeedResponse(
        posts=summaries,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


async def get_news_detail(news_id: str, user_id: str, database: AsyncSession) -> NewsPostDetail:
    repo = NewsRepository(database)
    user_repo = UserRepository(database)

    post = await repo.get_by_news_id(news_id)
    if not post:
        raise NewsPostNotFoundException()

    # Current user's reaction
    reaction_row = await repo.get_reaction(news_id, user_id)
    user_reaction = (
        ReactionType(reaction_row.reaction_type) if reaction_row else None
    )

    # Fetch all comments and assemble thread
    raw_comments = await repo.get_comments_for_post(news_id)
    comments = await _assemble_thread(raw_comments, user_repo)
    comment_count = len(raw_comments)

    return NewsPostDetail(
        news_id=post.news_id,
        report_id=post.report_id,
        title=post.title,
        harm_type=post.harm_type,
        content=post.content,
        context=post.context,
        upvotes=post.upvotes,
        downvotes=post.downvotes,
        user_reaction=user_reaction,
        comment_count=comment_count,
        comments=comments,
        created_at=post.created_at,
    )


async def _assemble_thread(comments: list[Comment], user_repo: UserRepository) -> list[CommentResponse]:
    """
    Build 2-level thread from flat list.
    Level 0 = top-level, level 1 = replies nested inside parent.
    """
    # Cache usernames to avoid N+1
    user_cache: dict[str, str] = {}

    async def get_username(uid: str) -> str:
        if uid not in user_cache:
            user = await user_repo.get_by_user_id(uid)
            user_cache[uid] = user.username if user else "Unknown"
        return user_cache[uid]

    top_level: list[CommentResponse] = []
    reply_map: dict[str, list[CommentResponse]] = {}

    for c in comments:
        username = await get_username(c.user_id)
        cr = CommentResponse(
            comment_id=c.comment_id,
            news_id=c.news_id,
            user_id=c.user_id,
            username=username,
            parent_id=c.parent_id,
            depth=c.depth,
            body=c.body,
            replies=[],
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        if c.parent_id is None:
            top_level.append(cr)
        else:
            reply_map.setdefault(c.parent_id, []).append(cr)

    # Attach replies to their parents
    for comment in top_level:
        comment.replies = reply_map.get(comment.comment_id, [])

    return top_level


async def add_comment(news_id: str, user_id: str, payload: CreateCommentRequest,
                      database: AsyncSession) -> CommentResponse:
    repo = NewsRepository(database)
    user_repo = UserRepository(database)

    post = await repo.get_by_news_id(news_id)
    if not post:
        raise NewsPostNotFoundException()

    depth = 0
    if payload.parent_id:
        parent = await repo.get_comment_by_id(payload.parent_id)
        if not parent:
            raise CommentNotFoundException()
        if parent.depth >= MAX_COMMENT_DEPTH:
            raise CommentDepthExceededException()
        depth = parent.depth + 1

    comment = await repo.create_comment(
        news_id=news_id,
        user_id=user_id,
        body=payload.body,
        parent_id=payload.parent_id,
        depth=depth,
    )

    user = await user_repo.get_by_user_id(user_id)
    username = user.username if user else "Unknown"

    return CommentResponse(
        comment_id=comment.comment_id,
        news_id=comment.news_id,
        user_id=comment.user_id,
        username=username,
        parent_id=comment.parent_id,
        depth=comment.depth,
        body=comment.body,
        replies=[],
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


async def react_to_post(news_id: str, user_id: str, payload: ReactRequest, database: AsyncSession, ) -> NewsPostDetail:
    repo = NewsRepository(database)

    post = await repo.get_by_news_id(news_id)
    if not post:
        raise NewsPostNotFoundException()

    previous, new_reaction = await repo.upsert_reaction(
        news_id=news_id,
        user_id=user_id,
        reaction_type=payload.reaction_type,
    )

    # Adjust counters — undo previous, apply new
    if previous == ReactionType.UP_VOTE and new_reaction == ReactionType.DOWN_VOTE:
        await repo.decrement_upvotes(news_id)
        await repo.increment_downvotes(news_id)
    elif previous == ReactionType.DOWN_VOTE and new_reaction == ReactionType.UP_VOTE:
        await repo.decrement_downvotes(news_id)
        await repo.increment_upvotes(news_id)
    elif previous is None and new_reaction == ReactionType.UP_VOTE:
        await repo.increment_upvotes(news_id)
    elif previous is None and new_reaction == ReactionType.DOWN_VOTE:
        await repo.increment_downvotes(news_id)
    # same reaction type re-submitted = no counter change (idempotent)

    return await get_news_detail(news_id, user_id, database)
