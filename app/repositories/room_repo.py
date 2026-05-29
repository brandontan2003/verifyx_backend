import random
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.room import Room, RoomParticipant, RoomStatus


def generate_room_code() -> str:
    """6-char alphanumeric code, uppercase, no ambiguous chars (0/O, 1/I/l)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(chars, k=6))


class RoomRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room(self, host_user_id: str, theme: str, max_players: int,
                          time_limit_seconds: int) -> Room:
        # Retry on rare code collision (probability ~1/33^6 ≈ negligible)
        for _ in range(5):
            code = generate_room_code()
            existing = await self.get_by_code(code)
            if not existing:
                break
        room = Room(
            host_user_id=host_user_id,
            code=code,
            theme=theme,
            max_players=max_players,
            time_limit_seconds=time_limit_seconds,
            status=RoomStatus.waiting
        )
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def add_participant(self, room_id: str, user_id: str, username: str) -> RoomParticipant:
        participant = RoomParticipant(room_id=room_id, user_id=user_id, username=username)
        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)
        return participant

    async def start_room(self, room_id: str, scenario: dict) -> Room:
        from datetime import datetime, timezone
        room = await self.get_room(room_id)
        room.status = RoomStatus.active
        room.scenario = scenario
        room.started_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def set_participant_challenge(self, room_id: str, user_id: str, challenge_id: str) -> None:
        await self.db.execute(
            update(RoomParticipant)
            .where(RoomParticipant.room_id == room_id, RoomParticipant.user_id == user_id)
            .values(challenge_id=challenge_id)
        )
        await self.db.commit()

    async def record_participant_result(self, room_id: str, user_id: str, is_correct: bool, xp_earned: int,
                                        time_taken_seconds: int) -> None:
        await self.db.execute(
            update(RoomParticipant)
            .where(RoomParticipant.room_id == room_id, RoomParticipant.user_id == user_id)
            .values(
                is_correct=is_correct,
                xp_earned=xp_earned,
                time_taken_seconds=time_taken_seconds,
                finished_at=datetime.now(timezone.utc)
            )
        )
        await self.db.commit()

    async def finish_room_if_all_done(self, room_id: str) -> bool:
        """
        Mark the room as finished if every participant has submitted.
        Returns True if the room was just finished.
        """
        result = await self.db.execute(
            select(func.count())
            .where(RoomParticipant.room_id == room_id, RoomParticipant.is_correct.is_(None))
        )
        pending = result.scalar_one()
        if pending == 0:
            await self.db.execute(
                update(Room)
                .where(Room.room_id == room_id)
                .values(status=RoomStatus.finished, finished_at=datetime.now(timezone.utc))
            )
            await self.db.commit()
            return True
        return False

    async def get_room(self, room_id: str) -> Room | None:
        result = await self.db.execute(select(Room).where(Room.room_id == room_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Room | None:
        result = await self.db.execute(select(Room).where(Room.code == code.upper()))
        return result.scalar_one_or_none()

    async def get_participants(self, room_id: str) -> list[RoomParticipant]:
        result = await self.db.execute(
            select(RoomParticipant).where(RoomParticipant.room_id == room_id)
        )
        return list(result.scalars().all())

    async def get_participant(self, room_id: str, user_id: str) -> RoomParticipant | None:
        result = await self.db.execute(
            select(RoomParticipant).where(
                RoomParticipant.room_id == room_id,
                RoomParticipant.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def participant_count(self, room_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(RoomParticipant.room_id == room_id)
        )
        return result.scalar_one()
