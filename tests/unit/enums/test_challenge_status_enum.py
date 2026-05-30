import pytest

from app.enums.ChallengeStatusEnum import ChallengeStatus


class TestChallengeStatus:
    def test_all_members_present(self):
        members = {m.value for m in ChallengeStatus}
        assert members == {"pending", "completed"}

    def test_is_string_enum(self):
        assert isinstance(ChallengeStatus.pending, str)
        assert ChallengeStatus.pending == "pending"

    def test_lookup_by_value(self):
        assert ChallengeStatus("pending") is ChallengeStatus.pending
        assert ChallengeStatus("completed") is ChallengeStatus.completed

    def test_pending_not_equal_completed(self):
        assert ChallengeStatus.pending != ChallengeStatus.completed

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ChallengeStatus("in_progress")
