import enum


class ChallengeStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
