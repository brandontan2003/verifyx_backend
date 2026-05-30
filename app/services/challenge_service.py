import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import client as ai
from app.core.cache.rate_limit.dependencies import _check_daily_limit, _increment_daily_limit
from app.core.exceptions.exceptions import ChallengeNotFoundException, InvalidAnswerFormatException
from app.core.logger import logger
from app.dto.challenge import (
    GenerateChallengeRequest, ChallengeResponse, ChallengeOption,
    SubmitAnswerRequest, AttemptResponse, DebriefDetail,
    AttemptSummary, ChallengeHistoryItem, ChallengeHistoryResponse,
)
from app.dto.progress import UpdateProgressRequest
from app.repositories.challenge_repo import ChallengeRepository
from app.repositories.user_repo import UserRepository
from app.services.progress_service import calculate_xp, update_progress


def build_challenge_response(challenge, room_id=None) -> ChallengeResponse:
    return ChallengeResponse(
        challenge_id=challenge.challenge_id,
        theme=challenge.theme,
        difficulty=challenge.difficulty,
        question_type=challenge.question_type,
        title=challenge.title,
        content=challenge.content,
        question=challenge.question,
        options=[ChallengeOption(**o) for o in challenge.options],
        tags=challenge.tags,
        room_id=room_id or challenge.room_id,
        created_at=challenge.created_at
    )


def valid_options_for(question_type: str) -> tuple[str, ...]:
    """Return the set of valid option IDs for a given question type."""
    if question_type == "true_false":
        return "A", "B"
    return "A", "B", "C", "D"


async def generate_challenge(user_id: str, payload: GenerateChallengeRequest,
                             database: AsyncSession) -> ChallengeResponse:
    challenge_repo = ChallengeRepository(database)
    await _check_daily_limit(user_id)

    # Build context for Claude's difficulty inference
    user_history = await challenge_repo.get_recent_tags(user_id, limit=10)
    attempt_count = await challenge_repo.count_completed_challenges(user_id)

    scenario = await ai.generate_scenario(
        theme=payload.theme,
        user_history=user_history,
        attempt_count=attempt_count
    )

    challenge = await challenge_repo.create_challenge(
        user_id=user_id,
        theme=scenario["theme"],
        difficulty=scenario["difficulty"],
        question_type=scenario["question_type"],
        title=scenario["title"],
        content=scenario["content"],
        question=scenario["question"],
        options=scenario["options"],
        correct_option_id=scenario["correct_option_id"],
        tags=scenario.get("tags"),
        room_id=None
    )
    await _increment_daily_limit(user_id)

    logger.info("Challenge generated: %s user=%s theme=%s type=%s diff=%d",
                challenge.challenge_id, user_id, payload.theme,
                challenge.question_type, challenge.difficulty)

    return build_challenge_response(challenge)


async def get_challenge(user_id: str, challenge_id: str, database: AsyncSession) -> ChallengeResponse:
    challenge_repo = ChallengeRepository(database)
    challenge = await challenge_repo.get_challenge_for_user(challenge_id, user_id)
    if not challenge:
        raise ChallengeNotFoundException()
    return build_challenge_response(challenge)


async def get_challenge_history(user_id: str, page: int, page_size: int,
                                database: AsyncSession) -> ChallengeHistoryResponse:
    challenge_repo = ChallengeRepository(database)
    rows, total = await challenge_repo.get_user_history(user_id, page, page_size)

    items = [
        ChallengeHistoryItem(
            challenge_id=challenge.challenge_id,
            theme=challenge.theme,
            difficulty=challenge.difficulty,
            question_type=challenge.question_type,
            title=challenge.title,
            status=challenge.status,
            created_at=challenge.created_at,
            attempts=[
                AttemptSummary(
                    attempt_id=a.attempt_id,
                    attempt_number=a.attempt_number,
                    is_correct=a.is_correct,
                    user_answer=a.user_answer,
                    xp_earned=a.xp_earned,
                    time_taken_seconds=a.time_taken_seconds,
                    submitted_at=a.submitted_at
                )
                for a in attempts
            ]
        )
        for challenge, attempts in rows
    ]

    return ChallengeHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0
    )


async def submit_answer(user_id: str, challenge_id: str, payload: SubmitAnswerRequest,
                        database: AsyncSession) -> AttemptResponse:
    challenge_repo = ChallengeRepository(database)
    user_repo = UserRepository(database)

    challenge = await challenge_repo.get_challenge_for_user(challenge_id, user_id)
    if not challenge:
        raise ChallengeNotFoundException()

    # Guard: true_false only accepts A or B
    valid_options = valid_options_for(challenge.question_type)
    if payload.user_answer not in valid_options:
        raise InvalidAnswerFormatException()

    # Count existing attempts to assign attempt_number
    existing_count = await challenge_repo.count_attempts(challenge_id)
    attempt_number = existing_count + 1
    already_correct = await challenge_repo.has_correct_attempt(challenge_id)

    options_map = {o["id"]: o["text"] for o in challenge.options}

    is_correct = payload.user_answer == challenge.correct_option_id
    confidence_score = 1.0
    reasoning = (
        f"User selected Option {payload.user_answer}; "
        f"correct option is Option {challenge.correct_option_id}."
    )
    # XP: full XP only on first correct answer; subsequent correct = 0; wrong = 0
    xp_earned = 0
    if is_correct and not already_correct:
        xp_earned = calculate_xp(
            difficulty=challenge.difficulty,
            time_taken=payload.time_taken_seconds,
            time_limit=payload.time_limit_seconds
        )

    try:
        debrief_raw = await ai.generate_debrief(
            scenario_content=challenge.content,
            question=challenge.question,
            question_type=challenge.question_type,
            correct_option_id=challenge.correct_option_id,
            correct_option_text=options_map.get(challenge.correct_option_id, ""),
            user_answer=payload.user_answer,
            user_answer_text=options_map.get(payload.user_answer, ""),
            is_correct=is_correct,
            difficulty=challenge.difficulty,
            time_taken=payload.time_taken_seconds,
            time_limit=payload.time_limit_seconds,
            attempt_number=attempt_number
        )
    except Exception:
        debrief_raw = {
            "summary": (
                "Your answer has been submitted. "
                f"The correct answer was Option {challenge.correct_option_id}."
            ),
            "key_lesson": "Check the evidence carefully before deciding.",
            "red_flags": ["unclear source", "missing evidence", "emotional wording"],
            "tip": "Compare the claim against a reliable source before trusting it."
        }
    # Persist attempt
    attempt = await challenge_repo.create_attempt(
        challenge_id=challenge_id,
        user_id=user_id,
        attempt_number=attempt_number,
        user_answer=payload.user_answer,
        is_correct=is_correct,
        confidence_score=confidence_score,
        reasoning=reasoning,
        time_taken_seconds=payload.time_taken_seconds,
        time_limit_seconds=payload.time_limit_seconds,
        xp_earned=xp_earned,
        debrief=debrief_raw
    )

    # Mark challenge completed on first correct answer
    if is_correct and not already_correct:
        await challenge_repo.mark_completed(challenge_id)

    if xp_earned > 0:
        update_progress_request = UpdateProgressRequest(
            difficulty=challenge.difficulty,
            time_limit_seconds=payload.time_limit_seconds,
            time_taken_seconds=payload.time_taken_seconds,
            is_perfect=is_correct
        )
        await update_progress(user_id, update_progress_request, database)

    updated_user = await user_repo.get_by_user_id(user_id)

    # Hook into room result tracking if this is a room challenge
    if challenge.room_id:
        from app.services.room_service import record_room_result
        await record_room_result(
            room_id=challenge.room_id,
            user_id=user_id,
            is_correct=is_correct,
            xp_earned=xp_earned,
            time_taken_seconds=payload.time_taken_seconds,
            database=database
        )

    correct_display = f"Option {challenge.correct_option_id} - {options_map.get(challenge.correct_option_id, '')}"

    logger.info("Attempt #%d on %s: user=%s type=%s correct=%s xp=%d",
                attempt_number, challenge_id, user_id, challenge.question_type, is_correct, xp_earned)

    return AttemptResponse(
        challenge_id=challenge_id,
        attempt_id=attempt.attempt_id,
        attempt_number=attempt_number,
        is_correct=is_correct,
        correct_answer_display=correct_display,
        user_answer=payload.user_answer,
        xp_earned=xp_earned,
        total_xp=updated_user.xp,
        streak=updated_user.streak,
        debrief=DebriefDetail(**debrief_raw)
    )
