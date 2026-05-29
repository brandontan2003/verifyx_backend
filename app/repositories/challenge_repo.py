from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge, ChallengeStatus, ChallengeAttempt, QuestionType


class ChallengeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_challenge(self, user_id: str, theme: str, difficulty: int, question_type: str, title: str,
                               content: str, question: str, options: list[dict], correct_option_id: str,
                               tags: list[str] | None, room_id: str | None = None) -> Challenge:
        challenge = Challenge(
            user_id=user_id,
            theme=theme,
            difficulty=difficulty,
            question_type=QuestionType(question_type),
            title=title,
            content=content,
            question=question,
            options=options,
            correct_option_id=correct_option_id,
            tags=tags or [],
            status=ChallengeStatus.pending,
            room_id=room_id
        )
        self.db.add(challenge)
        await self.db.commit()
        await self.db.refresh(challenge)
        return challenge

    async def mark_completed(self, challenge_id: str) -> None:
        challenge = await self.get_challenge(challenge_id)
        if challenge:
            challenge.status = ChallengeStatus.completed
            await self.db.commit()

    async def create_attempt(self, challenge_id: str, user_id: str, attempt_number: int, user_answer: str,
                             is_correct: bool, confidence_score: float, reasoning: str, time_taken_seconds: int,
                             time_limit_seconds: int, xp_earned: int, debrief: dict) -> ChallengeAttempt:
        attempt = ChallengeAttempt(
            challenge_id=challenge_id,
            user_id=user_id,
            attempt_number=attempt_number,
            user_answer=user_answer,
            is_correct=is_correct,
            confidence_score=round(confidence_score * 100),  # store as int 0-100
            reasoning=reasoning,
            time_taken_seconds=time_taken_seconds,
            time_limit_seconds=time_limit_seconds,
            xp_earned=xp_earned,
            debrief=debrief
        )
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt

    async def get_challenge(self, challenge_id: str) -> Challenge | None:
        result = await self.db.execute(
            select(Challenge).where(Challenge.challenge_id == challenge_id)
        )
        return result.scalar_one_or_none()

    async def get_challenge_for_user(self, challenge_id: str, user_id: str) -> Challenge | None:
        result = await self.db.execute(
            select(Challenge).where(
                Challenge.challenge_id == challenge_id,
                Challenge.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_attempts(self, challenge_id: str) -> list[ChallengeAttempt]:
        """All attempts for a challenge, chronological."""
        result = await self.db.execute(
            select(ChallengeAttempt)
            .where(ChallengeAttempt.challenge_id == challenge_id)
            .order_by(ChallengeAttempt.attempt_number)
        )
        return list(result.scalars().all())

    async def count_attempts(self, challenge_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(ChallengeAttempt.challenge_id == challenge_id)
        )
        return result.scalar_one()

    async def has_correct_attempt(self, challenge_id: str) -> bool:
        """True if the user has already answered this challenge correctly at least once."""
        result = await self.db.execute(
            select(func.count()).where(
                ChallengeAttempt.challenge_id == challenge_id,
                ChallengeAttempt.is_correct == True  # noqa: E712
            )
        )
        return result.scalar_one() > 0

    async def count_completed_challenges(self, user_id: str) -> int:
        """Total completed challenges for this user — used to calibrate difficulty."""
        result = await self.db.execute(
            select(func.count()).where(
                Challenge.user_id == user_id,
                Challenge.status == ChallengeStatus.completed
            )
        )
        return result.scalar_one()

    async def get_user_history(
            self,
            user_id: str,
            page: int,
            page_size: int
    ) -> tuple[list[tuple[Challenge, list[ChallengeAttempt]]], int]:
        """
        Returns (rows, total_count).
        Each row is (Challenge, [ChallengeAttempt, ...]) — all attempts per challenge.
        """
        count_result = await self.db.execute(
            select(func.count()).select_from(
                select(Challenge).where(Challenge.user_id == user_id).subquery()
            )
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        challenges_result = await self.db.execute(
            select(Challenge)
            .where(Challenge.user_id == user_id)
            .order_by(Challenge.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        challenges = list(challenges_result.scalars().all())

        # Batch-fetch all attempts for these challenges in one query
        challenge_ids = [c.challenge_id for c in challenges]
        attempts_result = await self.db.execute(
            select(ChallengeAttempt)
            .where(ChallengeAttempt.challenge_id.in_(challenge_ids))
            .order_by(ChallengeAttempt.challenge_id, ChallengeAttempt.attempt_number)
        )
        all_attempts = list(attempts_result.scalars().all())

        # Group attempts by challenge_id
        from collections import defaultdict
        attempts_by_challenge: dict[str, list[ChallengeAttempt]] = defaultdict(list)
        for a in all_attempts:
            attempts_by_challenge[a.challenge_id].append(a)

        return [(c, attempts_by_challenge[c.challenge_id]) for c in challenges], total

    async def get_recent_tags(self, user_id: str, limit: int = 10) -> list[str]:
        result = await self.db.execute(
            select(Challenge.tags)
            .where(Challenge.user_id == user_id, Challenge.status == ChallengeStatus.completed)
            .order_by(Challenge.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        tags: list[str] = []
        for tag_list in rows:
            if tag_list:
                tags.extend(tag_list)
        return tags

    async def get_challenges_by_room(self, room_id: str) -> list[Challenge]:
        result = await self.db.execute(
            select(Challenge).where(Challenge.room_id == room_id)
        )
        return list(result.scalars().all())
