from enum import Enum


class ContentType(str, Enum):
    URL = "url"
    MESSAGE = "message"
    IMAGE = "image"
    VIDEO = "video"
    OTHER = "other"


class HarmType(str, Enum):
    MISINFORMATION = "misinformation"
    SCAM = "scam"
    PHISHING = "phishing"
    DEEPFAKE = "deepfake"
    CYBERBULLYING = "cyberbullying"
    OTHER = "other"


class ReportStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
