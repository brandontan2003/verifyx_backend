"""
Unit tests for app/services/news_service.py

Covers:
  - _build_title
  - auto_publish_news_post (new post, idempotent)
  - get_news_feed
  - get_news_detail
  - _assemble_thread
  - add_comment (top-level, reply, depth exceeded, post not found, parent not found)
  - react_to_post (all counter permutations, post not found)
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import (
    CommentDepthExceededException,
    CommentNotFoundException,
    NewsPostNotFoundException,
)
from app.dto.news import CreateCommentRequest, ReactRequest
from app.enums.NewsEnum import ReactionType
from app.services.news_service import (
    _assemble_thread,
    _build_title,
    add_comment,
    auto_publish_news_post,
    get_news_detail,
    get_news_feed,
    react_to_post,
)

DB = AsyncMock()


def _make_post(news_id="news-1", report_id="rpt-1", title="Scam Alert",
               harm_type="scam", content="Long content here",
               upvotes=5, downvotes=1, context="Some context"):
    p = MagicMock()
    p.news_id = news_id
    p.report_id = report_id
    p.title = title
    p.harm_type = harm_type
    p.content = content
    p.context = context
    p.upvotes = upvotes
    p.downvotes = downvotes
    p.created_at = datetime(2024, 3, 1)
    return p


def _make_comment(comment_id="c-1", news_id="news-1", user_id="user-1",
                  body="Nice post", parent_id=None, depth=0):
    c = MagicMock()
    c.comment_id = comment_id
    c.news_id = news_id
    c.user_id = user_id
    c.body = body
    c.parent_id = parent_id
    c.depth = depth
    c.created_at = datetime(2024, 3, 2)
    c.updated_at = datetime(2024, 3, 2)
    return c


def _make_news_repo(post=None, list_result=None, comment_count=0, comments=None, reaction_row=None, created_post=None,
                    created_comment=None, upsert_reaction_result=None, parent_comment=None):
    repo = MagicMock()
    repo.get_by_news_id = AsyncMock(return_value=post)
    repo.get_by_report_id = AsyncMock(return_value=None)
    posts, total = list_result or ([], 0)
    repo.list_posts = AsyncMock(return_value=(posts, total))
    repo.count_comments_for_post = AsyncMock(return_value=comment_count)
    repo.get_comments_for_post = AsyncMock(return_value=comments or [])
    repo.get_reaction = AsyncMock(return_value=reaction_row)
    repo.create_news_post = AsyncMock(return_value=created_post or _make_post())
    repo.create_comment = AsyncMock(return_value=created_comment or _make_comment())
    repo.get_comment_by_id = AsyncMock(return_value=parent_comment)
    repo.upsert_reaction = AsyncMock(return_value=upsert_reaction_result or (None, ReactionType.UP_VOTE))
    repo.increment_upvotes = AsyncMock()
    repo.decrement_upvotes = AsyncMock()
    repo.increment_downvotes = AsyncMock()
    repo.decrement_downvotes = AsyncMock()
    return repo


def _make_user_repo(username="alice"):
    repo = MagicMock()
    user = MagicMock()
    user.username = username
    repo.get_by_user_id = AsyncMock(return_value=user)
    return repo


class TestBuildTitle:
    def test_short_content_no_ellipsis(self):
        title = _build_title("scam", "Short content")
        assert title == "Scam Alert: Short content"

    def test_long_content_truncated_with_ellipsis(self):
        long_content = "A" * 70
        title = _build_title("scam", long_content)
        assert "…" in title
        assert len(title.split(": ")[1]) <= 61  # 60 chars + ellipsis

    def test_underscore_harm_type_titlecased(self):
        title = _build_title("cyber_bullying", "Someone was harassed")
        assert title.startswith("Cyber Bullying Alert:")

    def test_exactly_60_chars_no_ellipsis(self):
        content = "X" * 60
        title = _build_title("phishing", content)
        assert "…" not in title


class TestAutoPublishNewsPost:
    @pytest.mark.asyncio
    async def test_creates_new_post(self):
        post = _make_post()
        repo = _make_news_repo(created_post=post)

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await auto_publish_news_post("rpt-1", "scam", "Scam content", "context", DB)

        repo.create_news_post.assert_awaited_once()
        assert result.news_id == "news-1"

    @pytest.mark.asyncio
    async def test_idempotent_returns_existing_post(self):
        existing = _make_post()
        repo = _make_news_repo()
        repo.get_by_report_id = AsyncMock(return_value=existing)

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await auto_publish_news_post("rpt-1", "scam", "Scam content", None, DB)

        repo.create_news_post.assert_not_awaited()
        assert result.news_id == "news-1"

    @pytest.mark.asyncio
    async def test_builds_title_from_harm_and_content(self):
        post = _make_post()
        repo = _make_news_repo(created_post=post)

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            await auto_publish_news_post("rpt-1", "phishing", "Fake login page detected", None, DB)

        call_kwargs = repo.create_news_post.call_args.kwargs
        assert "Phishing" in call_kwargs["title"]


class TestGetNewsFeed:
    @pytest.mark.asyncio
    async def test_returns_feed_with_summaries(self):
        posts = [_make_post("n1"), _make_post("n2")]
        repo = _make_news_repo(list_result=(posts, 2), comment_count=3)

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await get_news_feed(page=1, page_size=10, database=DB)

        assert result.total == 2
        assert len(result.posts) == 2

    @pytest.mark.asyncio
    async def test_truncates_long_content_in_summary(self):
        post = _make_post(content="X" * 300)
        repo = _make_news_repo(list_result=([post], 1))

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await get_news_feed(page=1, page_size=10, database=DB)

        assert result.posts[0].content.endswith("…")
        assert len(result.posts[0].content) <= 202  # 200 + "…"

    @pytest.mark.asyncio
    async def test_short_content_not_truncated(self):
        post = _make_post(content="Short")
        repo = _make_news_repo(list_result=([post], 1))

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await get_news_feed(page=1, page_size=10, database=DB)

        assert "…" not in result.posts[0].content

    @pytest.mark.asyncio
    async def test_has_more_flag(self):
        posts = [_make_post()]
        repo = _make_news_repo(list_result=(posts, 5))

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await get_news_feed(page=1, page_size=1, database=DB)

        assert result.has_more is True

    @pytest.mark.asyncio
    async def test_empty_feed(self):
        repo = _make_news_repo(list_result=([], 0))

        with patch("app.services.news_service.NewsRepository", return_value=repo):
            result = await get_news_feed(page=1, page_size=10, database=DB)

        assert result.posts == []
        assert result.total == 0


class TestGetNewsDetail:
    @pytest.mark.asyncio
    async def test_raises_not_found_when_post_missing(self):
        repo = _make_news_repo(post=None)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            with pytest.raises(NewsPostNotFoundException):
                await get_news_detail("news-x", "user-1", DB)

    @pytest.mark.asyncio
    async def test_returns_detail_with_reaction(self):
        post = _make_post()
        reaction = MagicMock()
        reaction.reaction_type = ReactionType.UP_VOTE
        repo = _make_news_repo(post=post, reaction_row=reaction, comments=[])

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            result = await get_news_detail("news-1", "user-1", DB)

        assert result.user_reaction == ReactionType.UP_VOTE

    @pytest.mark.asyncio
    async def test_user_reaction_none_when_not_reacted(self):
        post = _make_post()
        repo = _make_news_repo(post=post, reaction_row=None, comments=[])

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            result = await get_news_detail("news-1", "user-1", DB)

        assert result.user_reaction is None

    @pytest.mark.asyncio
    async def test_includes_assembled_comments(self):
        post = _make_post()
        c = _make_comment()
        repo = _make_news_repo(post=post, comments=[c])

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            result = await get_news_detail("news-1", "user-1", DB)

        assert result.comment_count == 1
        assert len(result.comments) == 1


class TestAssembleThread:
    @pytest.mark.asyncio
    async def test_top_level_comments_have_no_parent(self):
        c = _make_comment()
        ur = _make_user_repo()
        result = await _assemble_thread([c], ur)

        assert len(result) == 1
        assert result[0].parent_id is None

    @pytest.mark.asyncio
    async def test_replies_nested_under_parent(self):
        parent = _make_comment("c-1", depth=0)
        reply = _make_comment("c-2", parent_id="c-1", depth=1)
        ur = _make_user_repo()

        result = await _assemble_thread([parent, reply], ur)

        assert len(result) == 1
        assert len(result[0].replies) == 1
        assert result[0].replies[0].comment_id == "c-2"

    @pytest.mark.asyncio
    async def test_username_cached_to_avoid_n_plus_one(self):
        c1 = _make_comment("c-1", user_id="user-1")
        c2 = _make_comment("c-2", user_id="user-1")
        ur = _make_user_repo()

        await _assemble_thread([c1, c2], ur)

        # same user_id, should only fetch once
        assert ur.get_by_user_id.await_count == 1

    @pytest.mark.asyncio
    async def test_unknown_user_defaults_to_unknown_username(self):
        c = _make_comment(user_id="ghost")
        ur = MagicMock()
        ur.get_by_user_id = AsyncMock(return_value=None)

        result = await _assemble_thread([c], ur)
        assert result[0].username == "Unknown"


class TestAddComment:
    @pytest.mark.asyncio
    async def test_raises_post_not_found(self):
        repo = _make_news_repo(post=None)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            with pytest.raises(NewsPostNotFoundException):
                await add_comment("news-x", "user-1",
                                  CreateCommentRequest(body="Hello"), DB)

    @pytest.mark.asyncio
    async def test_top_level_comment_has_depth_zero(self):
        post = _make_post()
        comment = _make_comment(depth=0)
        repo = _make_news_repo(post=post, created_comment=comment)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            result = await add_comment("news-1", "user-1",
                                       CreateCommentRequest(body="Nice"), DB)

        assert result.depth == 0

    @pytest.mark.asyncio
    async def test_reply_depth_is_parent_depth_plus_one(self):
        post = _make_post()
        parent = _make_comment("parent-1", depth=0)
        reply = _make_comment("reply-1", parent_id="parent-1", depth=1)
        repo = _make_news_repo(post=post, parent_comment=parent, created_comment=reply)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            result = await add_comment(
                "news-1", "user-1",
                CreateCommentRequest(body="Replying", parent_id="parent-1"),
                DB
            )

        assert result.depth == 1

    @pytest.mark.asyncio
    async def test_raises_comment_not_found_when_parent_missing(self):
        post = _make_post()
        repo = _make_news_repo(post=post, parent_comment=None)
        repo.get_comment_by_id = AsyncMock(return_value=None)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            with pytest.raises(CommentNotFoundException):
                await add_comment(
                    "news-1", "user-1",
                    CreateCommentRequest(body="Reply", parent_id="gone-parent"),
                    DB
                )

    @pytest.mark.asyncio
    async def test_raises_depth_exceeded_when_parent_at_max_depth(self):
        post = _make_post()
        deep_parent = _make_comment("deep", depth=1)  # MAX_COMMENT_DEPTH = 1
        repo = _make_news_repo(post=post, parent_comment=deep_parent)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            with pytest.raises(CommentDepthExceededException):
                await add_comment(
                    "news-1", "user-1",
                    CreateCommentRequest(body="Too deep", parent_id="deep"),
                    DB
                )

    @pytest.mark.asyncio
    async def test_returns_comment_with_username(self):
        post = _make_post()
        comment = _make_comment()
        repo = _make_news_repo(post=post, created_comment=comment)
        ur = _make_user_repo(username="bob")

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=ur):
            result = await add_comment("news-1", "user-1",
                                       CreateCommentRequest(body="Test"), DB)

        assert result.username == "bob"


class TestReactToPost:
    @pytest.mark.asyncio
    async def test_raises_post_not_found(self):
        repo = _make_news_repo(post=None)

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            with pytest.raises(NewsPostNotFoundException):
                await react_to_post("news-x", "user-1",
                                    ReactRequest(reaction_type=ReactionType.UP_VOTE), DB)

    @pytest.mark.asyncio
    async def test_new_upvote_increments_upvotes(self):
        post = _make_post()
        repo = _make_news_repo(
            post=post,
            upsert_reaction_result=(None, ReactionType.UP_VOTE),
            comments=[]
        )

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            await react_to_post("news-1", "user-1",
                                ReactRequest(reaction_type=ReactionType.UP_VOTE), DB)

        repo.increment_upvotes.assert_awaited_once_with("news-1")
        repo.decrement_upvotes.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_downvote_increments_downvotes(self):
        post = _make_post()
        repo = _make_news_repo(
            post=post,
            upsert_reaction_result=(None, ReactionType.DOWN_VOTE),
            comments=[]
        )

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            await react_to_post("news-1", "user-1",
                                ReactRequest(reaction_type=ReactionType.DOWN_VOTE), DB)

        repo.increment_downvotes.assert_awaited_once_with("news-1")
        repo.decrement_downvotes.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upvote_to_downvote_flips_counters(self):
        post = _make_post()
        repo = _make_news_repo(
            post=post,
            upsert_reaction_result=(ReactionType.UP_VOTE, ReactionType.DOWN_VOTE),
            comments=[]
        )

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            await react_to_post("news-1", "user-1",
                                ReactRequest(reaction_type=ReactionType.DOWN_VOTE), DB)

        repo.decrement_upvotes.assert_awaited_once_with("news-1")
        repo.increment_downvotes.assert_awaited_once_with("news-1")

    @pytest.mark.asyncio
    async def test_downvote_to_upvote_flips_counters(self):
        post = _make_post()
        repo = _make_news_repo(
            post=post,
            upsert_reaction_result=(ReactionType.DOWN_VOTE, ReactionType.UP_VOTE),
            comments=[]
        )

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            await react_to_post("news-1", "user-1",
                                ReactRequest(reaction_type=ReactionType.UP_VOTE), DB)

        repo.decrement_downvotes.assert_awaited_once_with("news-1")
        repo.increment_upvotes.assert_awaited_once_with("news-1")

    @pytest.mark.asyncio
    async def test_same_reaction_submitted_again_no_counter_change(self):
        post = _make_post()
        repo = _make_news_repo(
            post=post,
            upsert_reaction_result=(ReactionType.UP_VOTE, ReactionType.UP_VOTE),
            comments=[]
        )

        with patch("app.services.news_service.NewsRepository", return_value=repo), \
                patch("app.services.news_service.UserRepository", return_value=_make_user_repo()):
            await react_to_post("news-1", "user-1",
                                ReactRequest(reaction_type=ReactionType.UP_VOTE), DB)

        repo.increment_upvotes.assert_not_awaited()
        repo.decrement_upvotes.assert_not_awaited()
