"""
Integration tests for /api/v1/progress endpoints.
"""
from datetime import date, timedelta, datetime

from app.enums.BadgeEnum import BadgeType
from app.enums.ErrorEnum import ErrorEnum
from tests.conftest import _seed_user, TEST_USER, AppTestClient, _seed_user_badge, _seed_badge, assert_error, \
    get_response_data


# Submit Progress
class TestSubmitProgress:
    async def test_returns_200_with_xp_earned(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/progress",
                json={"difficulty": 2, "time_taken_seconds": 10, "time_limit_seconds": 60, "is_perfect": False}
            )
        assert response.status_code == 200
        assert get_response_data(response)["xp_earned"] > 0

    async def test_streak_increments_on_consecutive_day(self, db_session, mock_ai):
        yesterday = date.today() - timedelta(days=1)
        await _seed_user(db_session, streak=3, last_activity_date=yesterday)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/progress",
                json={"difficulty": 1, "time_taken_seconds": 30, "time_limit_seconds": 60, "is_perfect": False}
            )
        assert response.status_code == 200
        assert get_response_data(response)["streak"] == 4

    async def test_returns_404_when_user_not_in_db(self, db_session):
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/progress",
                json={"difficulty": 2, "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_422_for_missing_difficulty(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/progress",
                json={"time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_422_for_zero_time_limit(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/progress",
                json={"difficulty": 2, "time_taken_seconds": 10, "time_limit_seconds": 0}
            )
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post(
                "/api/v1/progress",
                json={"difficulty": 2, "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Retrieve Progress
class TestGetProgress:
    async def test_returns_200_with_progress_data(self, db_session):
        await _seed_user(db_session, xp=150, streak=5, challenges_completed=10, perfect_scores=3)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/progress")
        assert response.status_code == 200
        expected_result = {"total_xp": 150, "streak": 5, "challenges_completed": 10, "perfect_scores": 3, "badges": []}
        assert get_response_data(response) == expected_result

    async def test_badges_field_is_present(self, db_session):
        await _seed_user(db_session)
        await _seed_badge(db_session)
        earned_at = datetime.now()
        await _seed_user_badge(db_session, earned_at=earned_at)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/progress")
        assert response.status_code == 200
        result = get_response_data(response)
        assert len(result["badges"]) == 1
        expected_response = {"total_xp": 0, "streak": 0, "challenges_completed": 0, "perfect_scores": 0, "badges": [
            {"badge_id": "badge-complete-1", "name": "badge-name", "description": "badge-description",
             "badge_type": BadgeType.completion, "threshold": 0, "earned_at": earned_at.isoformat()}]}
        assert result == expected_response

    async def test_badges_empty_for_new_user(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/progress")
        assert response.status_code == 200
        assert get_response_data(response)["badges"] == []

    async def test_returns_404_when_user_not_in_db(self, db_session):
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/progress")
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.get("/api/v1/progress")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)

    async def test_xp_increases_after_challenge_submission(self, db_session, mock_ai):
        await _seed_user(db_session, xp=0)
        # Generate and submit a challenge
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            gen = await client.post("/api/v1/challenge", json={"theme": "misinformation"})
            cid = get_response_data(gen)["challenge_id"]
            await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A", "time_taken_seconds": 5, "time_limit_seconds": 60}
            )
            response = await client.get("/api/v1/progress")
        assert get_response_data(response)["total_xp"] > 0
