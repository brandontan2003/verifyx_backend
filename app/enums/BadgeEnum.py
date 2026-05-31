import enum


class BadgeType(str, enum.Enum):
    xp = "xp"
    streak = "streak"
    completion = "completion"
