"""
Integration tests for /api/v1/user endpoints.
"""
from sqlalchemy import select

from app.enums.ErrorEnum import ErrorEnum
from app.models.user import User
from tests.conftest import _seed_user, TEST_USER, AppTestClient, assert_error, get_response_data


class TestGetUser:
    async def test_returns_200_with_user_data(self, db_session):
        await _seed_user(db_session, username="testuser")

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/user")

        assert response.status_code == 200
        expected_response = {"user_id": "existing-uid-0001", "email": "existing@test.com", "username": "testuser",
                             "xp": 0, "streak": 0}
        assert get_response_data(response) == expected_response

    async def test_returns_404_when_user_not_in_db(self, db_session):
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/user")
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as unauthed_client:
            response = await unauthed_client.get("/api/v1/user")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)

    async def test_response_contains_expected_fields(self, db_session):
        await _seed_user(db_session, xp=150, streak=5)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/user")
        assert response.status_code == 200
        expected_response = {"user_id": "existing-uid-0001", "email": "existing@test.com", "username": "existinguser",
                             "xp": 150, "streak": 5}
        assert get_response_data(response) == expected_response


class TestUpdateUser:
    async def test_returns_200_with_updated_username(self, db_session):
        await _seed_user(db_session, username="oldname")
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.put(
                "/api/v1/user", json={"username": "newname"}
            )
        assert response.status_code == 200
        expected_response = {"user_id": "existing-uid-0001", "email": "existing@test.com", "username": "newname",
                             "xp": 0, "streak": 0}
        assert get_response_data(response) == expected_response

    async def test_returns_404_when_user_not_in_db(self, db_session):
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.put(
                "/api/v1/user", json={"username": "newname"}
            )
        assert_error(response, ErrorEnum.USER_NOT_FOUND, 404)

    async def test_returns_422_for_missing_username(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.put("/api/v1/user", json={})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as unauthed_client:
            response = await unauthed_client.put(
                "/api/v1/user", json={"username": "newname"}
            )
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)

    async def test_cannot_update_other_users_data(self, db_session):
        """PUT /user always updates the authenticated user — never a user_id in the payload."""
        # Seed two distinct users
        await _seed_user(db_session, user_id="victim-uid-0001", email="victim@test.com", username="victim")
        await _seed_user(db_session, user_id=TEST_USER["sub"], email=TEST_USER["email"], username="attacker")

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            # Attempt to update a different user by slipping user_id into the payload
            response = await client.put(
                "/api/v1/user",
                json={"username": "hacked", "user_id": "victim-uid-0001"}
            )

        assert response.status_code == 200
        # Authenticated user's own record was updated
        expected_response = {"user_id": "existing-uid-0001", "email": "existing@test.com", "username": "hacked",
                             "xp": 0, "streak": 0}
        assert get_response_data(response) == expected_response

        # Victim's record is untouched — this is the actual security assertion
        result = await db_session.execute(select(User).where(User.user_id == "victim-uid-0001"))
        victim = result.scalar_one()
        assert victim.username == "victim"
