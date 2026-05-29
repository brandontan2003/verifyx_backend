from enum import Enum


class QuestionTheme(str, Enum):
    MISINFORMATION = "misinformation"
    SCAM = "scam"
    PHISHING = "phishing"
    CRISIS = "crisis"
    DATA_PRIVACY = "data privacy"
    DEEPFAKE = "deepfake"
    AI_AWARENESS = "AI awareness"
