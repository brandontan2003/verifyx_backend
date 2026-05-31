import pytest

from app.enums.ScopeEnum import ScopeType


class TestScopeType:
    def test_all_expected_scopes_present(self):
        values = {m.value for m in ScopeType}
        expected = {
            "challenge:read", "challenge:write",
            "room:read", "room:write",
            "progress:read", "progress:write",
            "leaderboard:read",
            "user:read", "user:write",
            "admin:read", "admin:write",
            "system:read", "system:write",
        }
        assert values == expected

    def test_scopes_follow_resource_colon_action_format(self):
        for scope in ScopeType:
            assert ":" in scope.value, f"{scope.name} does not follow 'resource:action' format"
            resource, action = scope.value.split(":", 1)
            assert resource, f"{scope.name} has empty resource part"
            assert action, f"{scope.name} has empty action part"

    def test_lookup_by_value(self):
        assert ScopeType("challenge:read") is ScopeType.CHALLENGE_READ
        assert ScopeType("admin:write") is ScopeType.ADMIN_WRITE
        assert ScopeType("system:read") is ScopeType.SYSTEM_READ

    def test_read_and_write_both_exist_for_main_resources(self):
        values = {m.value for m in ScopeType}
        for resource in ["challenge", "room", "progress", "user", "admin", "system"]:
            assert f"{resource}:read" in values, f"Missing {resource}:read"
            assert f"{resource}:write" in values, f"Missing {resource}:write"

    def test_all_scope_values_are_unique(self):
        values = [m.value for m in ScopeType]
        assert len(values) == len(set(values))

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ScopeType("report:write")
