import uuid

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, Enum, ForeignKey
from sqlalchemy.sql import func

from app.enums.ChallengeStatusEnum import ChallengeStatus
from app.enums.QuestionTypeEnum import QuestionType
from app.models.base import Base


class Challenge(Base):
    __tablename__ = "challenges"

    challenge_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    room_id = Column(String, ForeignKey("rooms.room_id"), nullable=True, index=True)
    theme = Column(String, nullable=False)
    difficulty = Column(Integer, nullable=False)  # Claude-assigned, 1-5
    question_type = Column(Enum(QuestionType), nullable=False)  # mcq | true_false
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    question = Column(String, nullable=False)
    options = Column(JSON, nullable=False)  # [{id, text}, ...]
    correct_option_id = Column(String, nullable=False)  # server_side_only
    tags = Column(JSON, nullable=True)
    status = Column(Enum(ChallengeStatus), nullable=False, server_default=ChallengeStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChallengeAttempt(Base):
    """
    Every submission attempt is stored — no idempotency block.
    attempt_number is 1-indexed per challenge, assigned at insert time.
    XP is awarded on first correct attempt only (enforced in service layer).
    """
    __tablename__ = "challenge_attempts"

    attempt_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    challenge_id = Column(String, ForeignKey("challenges.challenge_id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)  # 1, 2, 3, ...
    user_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    confidence_score = Column(Integer, nullable=False, server_default="0")  # 0-100, from Claude
    reasoning = Column(Text, nullable=True)  # Claude's evaluation reasoning
    time_taken_seconds = Column(Integer, nullable=False)
    time_limit_seconds = Column(Integer, nullable=False)
    xp_earned = Column(Integer, nullable=False, server_default="0")  # 0 if not first correct
    debrief = Column(JSON, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
