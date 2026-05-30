import pytest

from app.enums.NewsEnum import ReactionType


class TestReactionType:
    def test_all_members_present(self):
        members = {m.value for m in ReactionType}
        assert members == {"up_vote", "down_vote"}

    def test_is_string_enum(self):
        assert isinstance(ReactionType.UP_VOTE, str)
        assert ReactionType.UP_VOTE == "up_vote"

    def test_lookup_by_value(self):
        assert ReactionType("up_vote") is ReactionType.UP_VOTE
        assert ReactionType("down_vote") is ReactionType.DOWN_VOTE

    def test_up_vote_not_equal_down_vote(self):
        assert ReactionType.UP_VOTE != ReactionType.DOWN_VOTE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ReactionType("neutral")
