"""
Integration tests for /api/v1/leaderboard endpoints
"""
from sqlalchemy import select

from app.enums.ErrorEnum import ErrorEnum
from app.enums.RoleEnum import RoleType
from app.models.role import Role
from app.models.user import User
from tests.conftest import _seed_user, TEST_USER, AppTestClient, get_response_data, assert_error


async def _seed_users(db_session, count=5):
    """Seed multiple users with descending XP."""
    users = []
    role_result = await db_session.execute(select(Role.role_id).where(Role.name == RoleType.USER))
    role_id = role_result.scalar_one_or_none()

    for i in range(count):
        u = User(
            user_id=f"lb-uid-{i:04}",
            email=f"lbuser{i}@test.com",
            username=f"lbuser{i}",
            xp=(count - i) * 100,  # 500, 400, 300, 200, 100
            role_id=role_id,
        )
        db_session.add(u)
        users.append(u)
    await db_session.commit()
    return users


class TestLeaderboard:
    async def test_returns_200_with_leaderboard(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard")
        assert response.status_code == 200
        assert "leaderboard" in get_response_data(response)

    async def test_sorted_by_xp_descending(self, db_session):
        await _seed_user(db_session)
        await _seed_users(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard?limit=5")
        assert response.status_code == 200
        entries = get_response_data(response)["leaderboard"]
        assert len(entries) == 5
        xps = [e["xp"] for e in entries]
        assert xps == sorted(xps, reverse=True)

    async def test_limit_respected(self, db_session):
        await _seed_user(db_session)
        await _seed_users(db_session, count=10)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard?limit=3")
        assert response.status_code == 200
        entries = get_response_data(response)["leaderboard"]
        assert len(entries) == 3

    async def test_default_limit_is_50(self, db_session):
        await _seed_users(db_session, count=49)
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard")
        assert response.status_code == 200
        entries = get_response_data(response)["leaderboard"]
        assert len(entries) == 50

    async def test_returns_empty_list_when_no_users(self, db_session):
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard")
        assert response.status_code == 200
        entries = get_response_data(response)["leaderboard"]
        assert entries == []
        assert len(entries) == 0

    async def test_each_entry_has_expected_fields(self, db_session):
        await _seed_user(db_session, xp=100, streak=3)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard?limit=1")
        entry = get_response_data(response)["leaderboard"]
        assert len(entry) == 1
        expected_result = {"user_id": "existing-uid-0001", "username": "existinguser", "xp": 100, "streak": 3}
        assert entry[0] == expected_result

    async def test_limit_above_100_returns_422(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard?limit=101")
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_limit_below_1_returns_422(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/leaderboard?limit=0")
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_200_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as unauthed_client:
            response = await unauthed_client.get("/api/v1/leaderboard")
        assert response.status_code == 200
        assert len(get_response_data(response)["leaderboard"]) == 0

    async def test_top_user_is_first(self, db_session):
        await _seed_user(db_session)
        await _seed_users(db_session, count=5)
        async with AppTestClient(db_session) as client:
            response = await client.get("/api/v1/leaderboard?limit=10")
        assert response.status_code == 200
        entries = get_response_data(response)["leaderboard"]
        assert len(entries) == 6
        assert entries[0]["xp"] >= entries[-1]["xp"]
