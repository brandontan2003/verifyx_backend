import pytest

from app.enums.RoomStatusEnum import RoomStatus


class TestRoomStatus:
    def test_all_members_present(self):
        members = {m.value for m in RoomStatus}
        assert members == {"waiting", "active", "finished"}

    def test_is_string_enum(self):
        assert isinstance(RoomStatus.waiting, str)
        assert RoomStatus.waiting == "waiting"

    def test_lookup_by_value(self):
        assert RoomStatus("waiting") is RoomStatus.waiting
        assert RoomStatus("active") is RoomStatus.active
        assert RoomStatus("finished") is RoomStatus.finished

    def test_lifecycle_ordering(self):
        """waiting is the initial state, active is mid-game, finished is terminal."""
        statuses = [m.value for m in RoomStatus]
        assert "waiting" in statuses
        assert "active" in statuses
        assert "finished" in statuses

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            RoomStatus("in_progress")

    def test_waiting_not_equal_active(self):
        assert RoomStatus.waiting != RoomStatus.active

    def test_active_not_equal_finished(self):
        assert RoomStatus.active != RoomStatus.finished
