import enum

DMN_REGISTRY = {
    "XP_DMN": {
        "container_id": "code_exp26_rules",
        "model_namespace": "https://kiegroup.org/dmn/_43BF0ABF-346F-4749-9BDA-685403598107",
        "model_name": "Xp"
    }
}


class DmnRegistryKeyEnum(str, enum.Enum):
    XP_DMN = "XP_DMN"


class DecisionNameEnum(str, enum.Enum):
    CALCULATE_XP = "CalculateXP"
