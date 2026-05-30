from app.core.rules.rules_config import DmnRegistryKeyEnum, DecisionNameEnum, DMN_REGISTRY


class TestRulesConfig:
    def test_dmn_registry_contains_xp_dmn(self):
        assert "XP_DMN" in DMN_REGISTRY

    def test_xp_dmn_has_required_keys(self):
        entry = DMN_REGISTRY["XP_DMN"]
        assert "container_id" in entry
        assert "model_namespace" in entry
        assert "model_name" in entry

    def test_xp_dmn_model_name_is_xp(self):
        assert DMN_REGISTRY["XP_DMN"]["model_name"] == "Xp"

    def test_dmn_registry_key_enum_matches_registry(self):
        for key in DmnRegistryKeyEnum:
            assert key.value in DMN_REGISTRY

    def test_decision_name_enum_calculate_xp(self):
        assert DecisionNameEnum.CALCULATE_XP == "CalculateXP"
        assert DecisionNameEnum("CalculateXP") is DecisionNameEnum.CALCULATE_XP

    def test_dmn_registry_key_enum_is_string_enum(self):
        assert isinstance(DmnRegistryKeyEnum.XP_DMN, str)
        assert DmnRegistryKeyEnum.XP_DMN == "XP_DMN"
