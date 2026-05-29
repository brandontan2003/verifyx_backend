from sqlalchemy import Column, String, Integer, DateTime, Date, ForeignKey
from sqlalchemy.sql import func

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)  # Supabase/Cognito UUID
    email = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False)
    xp = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    challenges_completed = Column(Integer, default=0)
    perfect_scores = Column(Integer, default=0)
    last_activity_date = Column(Date, nullable=True)
    role_id = Column(String, ForeignKey("roles.role_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
