from datetime import datetime
from typing import Optional

from pydantic import field_validator

from app.dto.base import BaseDTO
from app.enums.NewsEnum import ReactionType


# ─── News feed ────────────────────────────────────────────────────────────────

class NewsPostSummary(BaseDTO):
    news_id: str
    report_id: str
    title: str
    harm_type: str
    content: str  # truncated at API layer for feed view
    upvotes: int
    downvotes: int
    comment_count: int
    created_at: datetime


class NewsFeedResponse(BaseDTO):
    posts: list[NewsPostSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


# ─── News detail ─────────────────────────────────────────────────────────────

class CommentResponse(BaseDTO):
    comment_id: str
    news_id: str
    user_id: str
    username: str
    parent_id: Optional[str]
    depth: int
    body: str
    replies: list["CommentResponse"] = []
    created_at: datetime
    updated_at: datetime


CommentResponse.model_rebuild()  # required for self-referential model


class NewsPostDetail(BaseDTO):
    news_id: str
    report_id: str
    title: str
    harm_type: str
    content: str
    context: Optional[str]
    upvotes: int
    downvotes: int
    user_reaction: Optional[ReactionType]  # current user's reaction, None if not reacted
    comment_count: int
    comments: list[CommentResponse]
    created_at: datetime


# ─── Requests ─────────────────────────────────────────────────────────────────

class CreateCommentRequest(BaseDTO):
    body: str
    parent_id: Optional[str] = None

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment body must not be empty")
        return v.strip()


class ReactRequest(BaseDTO):
    reaction_type: ReactionType


# ─── Verify ───────────────────────────────────────────────────────────────────

class VerifyRequest(BaseDTO):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content must not be empty")
        return v.strip()


class VerifyResponse(BaseDTO):
    verdict: str  # "legitimate" | "suspicious" | "scam" | "misinformation" | "insufficient_information"
    confidence: int  # 0-100
    is_low_confidence: bool  # True when confidence < 70
    red_flags: list[str]
    recommendation: str
    disclaimer: str
