from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import redis_store
from app.database import database
from app.dependencies import get_db, get_current_user
from app.enums.BadgeEnum import BadgeType
from app.enums.ChallengeStatusEnum import ChallengeStatus
from app.enums.ErrorEnum import ErrorEnum
from app.enums.QuestionTypeEnum import QuestionType
from app.enums.RoleEnum import RoleType
from app.enums.RoomStatusEnum import RoomStatus
from app.enums.ScopeEnum import ScopeType
from app.main import app as fastapi_app
from app.models.badge import UserBadges, Badges
from app.models.base import Base
from app.models.challenge import Challenge
from app.models.role import Role, Scope, RoleScope
from app.models.room import Room
from app.models.user import User

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_engine():
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    database.override_engine(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _seed_roles(engine)

    yield engine

    await engine.dispose()


async def _seed_roles(engine):
    """
    Insert user/admin/system roles once before any test runs.
    """
    # Role Ids
    ROLE_USER = "role-user-id-0001"
    ROLE_ADMIN = "role-admin-id-0001"
    ROLE_SYSTEM = "role-system-id-0001"

    SCOPE_IDS = {s.value: f"scope-{s.value.replace(':', '-')}" for s in ScopeType}

    USER_SCOPES = [
        ScopeType.CHALLENGE_READ,
        ScopeType.CHALLENGE_WRITE,
        ScopeType.ROOM_READ,
        ScopeType.ROOM_WRITE,
        ScopeType.PROGRESS_READ,
        ScopeType.PROGRESS_WRITE,
        ScopeType.LEADERBOARD_READ,
        ScopeType.USER_READ,
        ScopeType.USER_WRITE,
    ]
    ADMIN_SCOPES = USER_SCOPES + [ScopeType.ADMIN_READ, ScopeType.ADMIN_WRITE]
    SYSTEM_SCOPES = [ScopeType.SYSTEM_READ, ScopeType.SYSTEM_WRITE]

    ROLE_SCOPE_MAP = {
        ROLE_USER: USER_SCOPES,
        ROLE_ADMIN: ADMIN_SCOPES,
        ROLE_SYSTEM: SYSTEM_SCOPES,
    }

    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Insert Roles
        for role_id, name, description in [
            (ROLE_USER, "user", "Standard player"),
            (ROLE_ADMIN, "admin", "Administrator"),
            (ROLE_SYSTEM, "system", "System service account"),
        ]:
            session.add(Role(role_id=role_id, name=name, description=description))

        # Insert Scopes
        for scope in ScopeType:
            session.add(Scope(scope_id=SCOPE_IDS[scope.value], name=scope))

        # Insert Role and Scopes mapping
        for role_id, scopes in ROLE_SCOPE_MAP.items():
            for scope in scopes:
                session.add(RoleScope(role_id=role_id, scope_id=SCOPE_IDS[scope.value]))
        await session.commit()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """
    Per-test session wrapped in a SAVEPOINT.
    Rolled back after each test — zero data leakage between tests.
    """
    async with db_engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()

        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session

        await session.close()
        await conn.rollback()


# Redis mock
class MockRedisState:
    def __init__(self):
        self.store = {}
        self.force_limit = False


@pytest_asyncio.fixture(autouse=True)
def mock_redis():
    state = MockRedisState()

    async def incr(key):
        # default behavior = safe (never hit limit unless forced)
        state.store[key] = state.store.get(key, 0) + 1

        if state.force_limit:
            return 999  # always trigger 429

        if not state.force_limit:
            return 0

        return state.store[key]

    async def expire(key, ttl):
        return True

    async def get(key):
        # No limit forced → key doesn't exist → return None (under limit)
        if not state.force_limit:
            return None
        # Limit forced → simulate counter already at 1 (hits DAILY_SOLO_LIMIT)
        return b"1"

    async def ttl(key):
        return 60

    redis = AsyncMock()
    redis.incr.side_effect = incr
    redis.get.side_effect = get
    redis.expire.side_effect = expire
    redis.ttl.side_effect = ttl

    redis_store.init_redis(redis)

    # expose control hook to tests
    redis._state = state

    yield redis


_AI_CLIENT = "app.ai.client"
_RULES_ENGINE = "app.services.rules_service.RulesEngine"

_MOCK_XP_RESULT = MagicMock()
_MOCK_XP_RESULT.decision_name = "CALCULATE_XP"
_MOCK_XP_RESULT.status = "SUCCEEDED"
_MOCK_XP_RESULT.result = 20

MOCK_SCENARIO = {
    "title": "Test Scenario",
    "content": "A social media post claims scientists discovered water on Mars.",
    "question": "Is this claim supported by peer-reviewed evidence?",
    "question_type": "true_false",
    "options": [{"id": "A", "text": "True"}, {"id": "B", "text": "False"}],
    "correct_option_id": "A",
    "difficulty": 1,
    "theme": "misinformation",
    "tags": ["science", "social-media"],
}

MOCK_EVALUATION = {
    "is_correct": True,
    "confidence_score": 1.0,
    "reasoning": "Option A is correct.",
}

MOCK_DEBRIEF = {
    "summary": "The claim is supported by peer-reviewed evidence.",
    "key_lesson": "Always check the primary source.",
    "red_flags": ["anonymous author", "no citations", "emotional language"],
    "tip": "Search for the original study before sharing.",
}


@pytest.fixture
def mock_ai():
    """
    Replace all three AI calls with deterministic stubs.

    generate_scenario  -> MOCK_SCENARIO  (true_false, correct=A, difficulty=1)
    evaluate_response  -> MOCK_EVALUATION (is_correct=True)
    generate_debrief   -> MOCK_DEBRIEF

    The correct_option_id is "A" and the mock evaluation always returns
    is_correct=True, so submitting user_answer="A" awards XP every time.
    Use user_answer="B" in tests that need an incorrect attempt.
    """
    with patch(f"{_AI_CLIENT}.generate_scenario", new=AsyncMock(return_value=MOCK_SCENARIO)), \
            patch(f"{_AI_CLIENT}.evaluate_response", new=AsyncMock(return_value=MOCK_EVALUATION)), \
            patch(f"{_AI_CLIENT}.generate_debrief", new=AsyncMock(return_value=MOCK_DEBRIEF)), \
            patch(f"{_AI_CLIENT}.complete_with_fallback", new=AsyncMock(return_value="")), \
            patch(f"{_RULES_ENGINE}.execute", return_value=[_MOCK_XP_RESULT]):
        yield


class AppTestClient:
    def __init__(self, db_session: AsyncSession, auth_user: dict | None = None):
        self._db_session = db_session
        self._auth_user = auth_user
        self._http: AsyncClient | None = None

    async def __aenter__(self) -> "AppTestClient":
        fastapi_app.dependency_overrides[get_db] = lambda: self._db_session

        if self._auth_user:
            fastapi_app.dependency_overrides[get_current_user] = lambda: self._auth_user

        self._http = AsyncClient(
            transport=ASGITransport(app=fastapi_app),
            base_url="http://test",
        )
        await self._http.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._http.__aexit__(*args)
        fastapi_app.dependency_overrides.clear()

    def _apply_cookies(self, cookies: dict | None) -> None:
        """Set cookies directly on the client instance to avoid the httpx
        per-request cookies deprecation warning."""
        if cookies:
            self._http.cookies.update(cookies)

    # Convenience methods — cookies are set on the client, not per-request.
    async def post(self, url: str, *, cookies: dict | None = None, **kwargs):
        self._apply_cookies(cookies)
        return await self._http.post(url, **kwargs)

    async def put(self, url: str, *, cookies: dict | None = None, **kwargs):
        self._apply_cookies(cookies)
        return await self._http.put(url, **kwargs)

    async def get(self, url: str, *, cookies: dict | None = None, **kwargs):
        self._apply_cookies(cookies)
        return await self._http.get(url, **kwargs)

    async def delete(self, url: str, *, cookies: dict | None = None, **kwargs):
        self._apply_cookies(cookies)
        return await self._http.delete(url, **kwargs)


# Auth Payload
TEST_USER = {
    "sub": "existing-uid-0001",
    "email": "existing@test.com",
    "role": "user",
}
TEST_ADMIN = {
    "sub": "test-admin-uid-0001",
    "email": "testadmin@example.com",
    "role": "admin",
}


# Seed helpers
async def _seed_user(db_session: AsyncSession, user_id: str = "existing-uid-0001", email: str = "existing@test.com",
                     username: str = "existinguser", xp: int = 0, streak: int = 0, challenges_completed: int = 0,
                     perfect_scores: int = 0, last_activity_date: date = None):
    """Insert a user directly — bypasses the auth provider."""
    role_result = await db_session.execute(select(Role.role_id).where(Role.name == RoleType.USER))
    role_id = role_result.scalar_one_or_none()

    user = User(user_id=user_id, email=email, username=username, role_id=role_id, xp=xp, streak=streak,
                challenges_completed=challenges_completed, perfect_scores=perfect_scores,
                last_activity_date=last_activity_date)
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_badge(db_session: AsyncSession, badge_id: str = "badge-complete-1", name: str = "badge-name",
                      description: str = "badge-description", badge_type: str = BadgeType.completion,
                      threshold: int = 0) -> None:
    """
    Award a badge row to a user directly.
    """
    db_session.add(
        Badges(badge_id=badge_id, name=name, description=description, badge_type=badge_type, threshold=threshold))
    await db_session.commit()


async def _seed_user_badge(db_session: AsyncSession, user_id: str = "existing-uid-0001",
                           badge_id: str = "badge-complete-1", earned_at: datetime = datetime.now()) -> None:
    """
    Award a badge row to a user directly.
    """
    db_session.add(UserBadges(user_id=user_id, badge_id=badge_id, earned_at=earned_at))
    await db_session.commit()


async def seed_challenge(db_session, user_id="existing-uid-0001", question_type="true_false", status="pending",
                         room_id=None):
    """Insert a challenge row and return it."""
    challenge = Challenge(
        challenge_id="ch-test-001",
        user_id=user_id,
        room_id=room_id,
        theme="misinformation",
        difficulty=2,
        question_type=QuestionType(question_type),
        title="Test Challenge",
        content="A viral post makes an extraordinary claim.",
        question="Is this misinformation?",
        options=[{"id": "A", "text": "True"}, {"id": "B", "text": "False"}],
        correct_option_id="A",
        tags=["health"],
        status=ChallengeStatus(status),
    )
    db_session.add(challenge)
    await db_session.commit()
    return challenge


async def seed_room(db_session, host_user_id="existing-uid-0001", status="waiting"):
    """Insert a room row and return it."""
    room = Room(
        room_id="room-test-001",
        code="TST001",
        host_user_id=host_user_id,
        theme="misinformation",
        max_players=8,
        time_limit_seconds=60,
        status=RoomStatus(status),
        scenario=MOCK_SCENARIO,
    )
    db_session.add(room)
    await db_session.commit()
    return room


def get_response_data(response):
    data = response.json()

    assert isinstance(data, dict), data
    assert "result" in data, data

    return data["result"]


def assert_error(response, expected_error_enum, status_code=None):
    if status_code:
        assert response.status_code == status_code, response.json()

    result = get_response_data(response)

    assert "errors" in result, result
    assert isinstance(result["errors"], list), result

    errors = result["errors"]
    assert len(errors) > 0, result

    # Match by error_code
    matched = [
        e for e in errors
        if e.get("error_code") == expected_error_enum.error_code
    ]

    assert matched, f"Expected error {expected_error_enum}, got {errors}"

    # Skip strict error_message assertion for validation errors, as they may include dynamic or field-specific messages
    if expected_error_enum != ErrorEnum.VALIDATION_ERROR:
        error = matched[0]
        assert error.get("error_message") == expected_error_enum.error_message
