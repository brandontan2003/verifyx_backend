import uuid

from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.enums.BadgeEnum import BadgeType
from app.models.base import Base


class Badges(Base):
    __tablename__ = "badges"

    badge_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    badge_type = Column(Enum(BadgeType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    threshold = Column(Integer, nullable=False)

    user_badges = relationship("UserBadges", back_populates="badges")


class UserBadges(Base):
    __tablename__ = "user_badges"

    user_id = Column(String, ForeignKey("users.user_id"), primary_key=True)
    badge_id = Column(String, ForeignKey("badges.badge_id"), primary_key=True)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    badges = relationship("Badges", back_populates="user_badges")
