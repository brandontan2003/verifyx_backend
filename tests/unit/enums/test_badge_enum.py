import pytest

from app.enums.BadgeEnum import BadgeType


class TestBadgeType:
    def test_all_members_present(self):
        members = {m.value for m in BadgeType}
        assert members == {"xp", "streak", "completion", "perfect"}

    def test_is_string_enum(self):
        assert isinstance(BadgeType.xp, str)
        assert BadgeType.xp == "xp"

    def test_each_member_equals_its_value(self):
        for member in BadgeType:
            assert member == member.value

    def test_lookup_by_value(self):
        assert BadgeType("xp") is BadgeType.xp
        assert BadgeType("streak") is BadgeType.streak
        assert BadgeType("completion") is BadgeType.completion
        assert BadgeType("perfect") is BadgeType.perfect

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            BadgeType("nonexistent")
