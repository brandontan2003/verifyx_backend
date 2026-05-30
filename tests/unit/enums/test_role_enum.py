import pytest

from app.enums.RoleEnum import RoleType


class TestRoleType:
    def test_all_members_present(self):
        members = {m.value for m in RoleType}
        assert members == {"admin", "user", "system"}

    def test_lookup_by_value(self):
        assert RoleType("admin") is RoleType.ADMIN
        assert RoleType("user") is RoleType.USER
        assert RoleType("system") is RoleType.SYSTEM

    def test_not_string_enum(self):
        # RoleType does NOT inherit from str — value comparison must use .value
        assert RoleType.ADMIN.value == "admin"

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            RoleType("superuser")
