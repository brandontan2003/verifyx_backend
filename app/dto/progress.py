from datetime import datetime

from app.dto.base import BaseDTO
from app.enums.BadgeEnum import BadgeType


class CreateBadgeRequest(BaseDTO):
    name: str
    description: str
    badge_type: BadgeType
    threshold: int


class UpdateBadgeRequest(BaseDTO):
    name: str
    description: str


class AdminBadgeResponse(BaseDTO):
    badge_id: str
    name: str
    description: str
    badge_type: BadgeType
    threshold: int


class RetrieveAllBadgesResponse(BaseDTO):
    badges: list[AdminBadgeResponse]


class BadgeResponse(BaseDTO):
    badge_id: str
    name: str
    description: str
    badge_type: BadgeType
    threshold: int
    earned_at: datetime


class UpdateProgressRequest(BaseDTO):
    difficulty: int  # 1-5
    time_taken_seconds: int  # actual time taken
    time_limit_seconds: int  # total time allowed
    is_perfect: bool  # scored 100%


class UpdateProgressResponse(BaseDTO):
    xp_earned: int
    total_xp: int
    streak: int
    new_badges: list[BadgeResponse]


class UserProgressResponse(BaseDTO):
    total_xp: int
    streak: int
    challenges_completed: int
    perfect_scores: int
    badges: list[BadgeResponse]
