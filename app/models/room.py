import uuid

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.sql import func

from app.enums.RoomStatusEnum import RoomStatus
from app.models.base import Base


class Room(Base):
    """
    A multiplayer room. One shared scenario is generated and stored here.
    Every participant gets their own Challenge row linked via room_id so
    per-player answers/debriefs are isolated.
    """
    __tablename__ = "rooms"

    room_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(6), unique=True, nullable=False)  # human-readable join code e.g. "XK9F2A"
    host_user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    theme = Column(String, nullable=False)
    max_players = Column(Integer, nullable=False, default=8)
    time_limit_seconds = Column(Integer, nullable=False, default=60)
    status = Column(Enum(RoomStatus), nullable=False, server_default=RoomStatus.waiting)

    # Snapshot of the shared scenario — generated once when host starts the room
    scenario = Column(JSON, nullable=True)  # full Claude output, set on start

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class RoomParticipant(Base):
    """
    Tracks who is in a room and their result once they submit.
    This is the source of truth for the leaderboard within a room.
    """
    __tablename__ = "room_participants"

    room_id = Column(String, ForeignKey("rooms.room_id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), primary_key=True)
    username = Column(String, nullable=False)
    challenge_id = Column(String, ForeignKey("challenges.challenge_id"), nullable=True)  # set on start
    is_correct = Column(Boolean, nullable=True)  # null = not yet submitted
    xp_earned = Column(Integer, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
