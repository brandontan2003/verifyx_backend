import uuid

from sqlalchemy import Column, String, Text, DateTime, Integer, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.enums.NewsEnum import ReactionType
from app.models.base import Base


class NewsPost(Base):
    __tablename__ = "news_posts"

    news_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String, ForeignKey("reports.report_id"), nullable=False, unique=True, index=True)
    title = Column(String, nullable=False)
    harm_type = Column(String, nullable=False)  # mirrored from report for fast queries
    content = Column(Text, nullable=False)  # mirrored from report.content
    context = Column(Text, nullable=True)  # mirrored from report.context
    upvotes = Column(Integer, nullable=False, server_default="0")
    downvotes = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Comment(Base):
    __tablename__ = "comments"

    comment_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    news_id = Column(String, ForeignKey("news_posts.news_id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    parent_id = Column(String, ForeignKey("comments.comment_id"), nullable=True, index=True)
    # depth enforced at service layer: None = level 1, set = level 2 (max)
    depth = Column(Integer, nullable=False, server_default="0")  # 0 = top-level, 1 = reply
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NewsReaction(Base):
    """
    One row per user per news post — mutually exclusive upvote/downvote.
    UniqueConstraint ensures a user can only have one reaction per post.
    """
    __tablename__ = "news_reactions"
    __table_args__ = (
        UniqueConstraint("news_id", "user_id", name="uq_news_reaction_user"),
    )

    reaction_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    news_id = Column(String, ForeignKey("news_posts.news_id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    reaction_type = Column(
        Enum(ReactionType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
