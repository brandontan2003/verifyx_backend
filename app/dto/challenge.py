from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from app.dto.base import BaseDTO
from app.dto.progress import BadgeResponse
from app.enums.QuestionTypeEnum import QuestionType
from app.services.code_service import retrieve_theme


class GenerateChallengeRequest(BaseDTO):
    theme: str

    @field_validator("theme")
    @classmethod
    def theme_not_empty(cls, val: str) -> str:
        val = val.strip().lower()
        theme_accepted = retrieve_theme()
        if not val:
            raise ValueError("theme must not be blank")
        if val not in theme_accepted:
            raise ValueError(f"Invalid theme '{val}'. Accepted values are: {', '.join(theme_accepted)}")
        return val


class SubmitAnswerRequest(BaseDTO):
    """
    user_answer accepts either an option ID ("A"/"B"/"C"/"D") for MCQ
    or a free-text string for free_text questions.
    Validation of MCQ format is deferred to the service layer where
    question_type is known.
    """
    user_answer: str
    time_taken_seconds: int
    time_limit_seconds: int

    @field_validator("user_answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_answer must not be blank")
        return v.strip()

    @field_validator("time_taken_seconds", "time_limit_seconds")
    @classmethod
    def positive_time(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("time values must be positive")
        return v


class ChallengeOption(BaseDTO):
    id: str
    text: str


class ChallengeResponse(BaseDTO):
    """
    Returned when a challenge is generated.
    correct_option_id is intentionally excluded — revealed only after submission.
    question_type tells the frontend whether to render 4 options or 2 (True/False).
    """
    challenge_id: str
    theme: str
    difficulty: int
    question_type: QuestionType
    title: str
    content: str
    question: str
    options: list[ChallengeOption]
    tags: Optional[list[str]] = None
    room_id: Optional[str] = None
    created_at: datetime


class DebriefDetail(BaseDTO):
    summary: str
    key_lesson: str
    red_flags: list[str]
    tip: str


class AttemptResponse(BaseDTO):
    """Returned after every submission attempt."""
    challenge_id: str
    attempt_id: str
    attempt_number: int
    is_correct: bool
    correct_answer_display: str  # "Option A — True" etc., revealed post-submit
    user_answer: str
    xp_earned: int  # 0 if not first correct attempt
    total_xp: int
    streak: int
    debrief: DebriefDetail
    new_badges: list[BadgeResponse] = Field(default_factory=list)


class AttemptSummary(BaseDTO):
    """Lightweight attempt record for history views."""
    attempt_id: str
    attempt_number: int
    is_correct: bool
    user_answer: str
    xp_earned: int
    time_taken_seconds: int
    submitted_at: datetime


class ChallengeHistoryItem(BaseDTO):
    challenge_id: str
    theme: str
    difficulty: int
    question_type: str
    title: str
    status: str
    created_at: datetime
    attempts: list[AttemptSummary] = []


class ChallengeHistoryResponse(BaseDTO):
    items: list[ChallengeHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int
