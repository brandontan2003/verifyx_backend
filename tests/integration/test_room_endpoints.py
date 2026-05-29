"""
Integration tests for /api/v1/room endpoints.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.ErrorEnum import ErrorEnum
from app.enums.RoleEnum import RoleType
from app.enums.RoomStatusEnum import RoomStatus
from app.models.role import Role
from app.models.user import User
from tests.conftest import seed_room, _seed_user, AppTestClient, TEST_ADMIN, TEST_USER, get_response_data, assert_error

CREATE_PAYLOAD = {
    "theme": "misinformation",
    "max_players": 8,
    "time_limit_seconds": 60,
}


async def create_admin(db_session: AsyncSession):
    role_result = await db_session.execute(select(Role.role_id).where(Role.name == RoleType.ADMIN))
    role_id = role_result.scalar_one_or_none()

    admin_user = User(
        user_id="test-admin-uid-0001",
        email="testadmin@example.com",
        username="admin",
        role_id=role_id
    )
    db_session.add(admin_user)
    await db_session.commit()


# Create Room
class TestCreateRoom:
    async def test_returns_200_with_room_data(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
        assert response.status_code == 200
        data = get_response_data(response)
        assert data["room_id"] is not None
        assert data["code"] is not None
        assert data["participants"] is not None
        assert data["participants"][0]["user_id"] == TEST_USER["sub"]

    async def test_code_is_6_characters(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
        assert response.status_code == 200
        assert len(get_response_data(response)["code"]) == 6

    async def test_host_auto_joins(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
        participants = get_response_data(response)["participants"]
        assert len(participants) == 1
        assert participants[0]["user_id"] == TEST_USER["sub"]

    async def test_status_is_waiting(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
        assert response.status_code == 200
        assert get_response_data(response)["status"] == RoomStatus.waiting

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Join Room
class TestJoinRoom:
    async def test_returns_200_with_valid_code(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            code = get_response_data(create)["code"]
            response = await client.post("/api/v1/room/join", params={"code": code})
        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    async def test_returns_404_for_invalid_code(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/room/join", params={"code": "XXXXXX"})
        assert_error(response, ErrorEnum.ROOM_NOT_FOUND, 404)

    async def test_is_idempotent_when_already_joined(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            code = get_response_data(create)["code"]

            r1 = await client.post("/api/v1/room/join", params={"code": code})
            response_2 = await client.post("/api/v1/room/join", params={"code": code})
        assert r1.status_code == 200
        assert response_2.status_code == 200
        # Still only one participant
        assert len(get_response_data(response_2)["participants"]) == 1

    async def test_returns_409_when_room_full(self, db_session):
        from app.models.room import RoomParticipant

        await _seed_user(db_session)
        room = await seed_room(db_session)

        # Fill the room to max_players=8 with dummy participants
        for i in range(8):
            p = RoomParticipant(
                room_id=room.room_id,
                user_id=f"dummy-uid-{i:04}",
                username=f"dummy{i}"
            )
            db_session.add(p)
        await db_session.commit()
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/room/join", params={"code": room.code}
            )
        assert_error(response, ErrorEnum.ROOM_FULL, 409)

    async def test_returns_409_when_room_already_active(self, db_session):
        await _seed_user(db_session)
        room = await seed_room(db_session, status="active")
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/room/join", params={"code": room.code}
            )
        assert_error(response, ErrorEnum.ROOM_ALREADY_ACTIVE, 409)


# Retrieve Room
class TestGetRoom:
    async def test_returns_200_with_room_state(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

            response = await client.get(f"/api/v1/room/{room_id}")
        assert response.status_code == 200
        assert get_response_data(response)["room_id"] == room_id

    async def test_returns_404_for_nonexistent_room(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/room/does-not-exist")
        assert_error(response, ErrorEnum.ROOM_NOT_FOUND, 404)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.get("/api/v1/room/any-id")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Start Room
class TestStartRoom:
    async def test_returns_200_with_challenge_for_host(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

            response = await client.post(f"/api/v1/room/{room_id}/start")
        assert response.status_code == 200
        data = get_response_data(response)
        assert data["status"] == RoomStatus.active
        assert data["challenge"] is not None

    async def test_challenge_has_no_correct_option_id(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

            response = await client.post(f"/api/v1/room/{room_id}/start")
        assert response.status_code == 200
        challenge = get_response_data(response)["challenge"]
        assert "correct_option_id" not in challenge

    async def test_returns_409_when_started_twice(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

            await client.post(f"/api/v1/room/{room_id}/start")
            response = await client.post(f"/api/v1/room/{room_id}/start")
        assert_error(response, ErrorEnum.ROOM_ALREADY_ACTIVE, 409)

    async def test_returns_403_when_not_host(self, db_session):
        """admin_client has a different sub — should be rejected as non-host."""
        await _seed_user(db_session)
        # Seed admin user too
        await create_admin(db_session)

        # Host creates the room
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

        # Non-host tries to start
        async with AppTestClient(db_session, auth_user=TEST_ADMIN) as admin_client:
            response = await admin_client.post(f"/api/v1/room/{room_id}/start")
        assert_error(response, ErrorEnum.NOT_ROOM_HOST, 403)

    async def test_returns_404_for_nonexistent_room(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/room/does-not-exist/start")
        assert_error(response, ErrorEnum.ROOM_NOT_FOUND, 404)


class TestGetRoomChallenge:
    async def test_returns_challenge_after_start(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]
            await client.post(f"/api/v1/room/{room_id}/start")

            response = await client.get(f"/api/v1/room/{room_id}/challenge")
        assert response.status_code == 200
        assert "challenge_id" in get_response_data(response)

    async def test_challenge_has_no_correct_option_id(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]
            await client.post(f"/api/v1/room/{room_id}/start")

            response = await client.get(f"/api/v1/room/{room_id}/challenge")
        assert "correct_option_id" not in get_response_data(response)

    async def test_returns_409_before_room_starts(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

            response = await client.get(f"/api/v1/room/{room_id}/challenge")
        assert_error(response, ErrorEnum.ROOM_NOT_ACTIVE, 409)

    async def test_returns_404_for_nonexistent_room(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/room/does-not-exist/challenge")
        assert_error(response, ErrorEnum.ROOM_NOT_FOUND, 404)


# Room Leaderboard
class TestRoomLeaderboard:
    async def test_returns_empty_entries_before_any_submission(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]

            response = await client.get(f"/api/v1/room/{room_id}/leaderboard")
        assert response.status_code == 200
        assert response.json()["result"]["entries"] == []

    async def test_entry_appears_after_submission(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]
            start = await client.post(f"/api/v1/room/{room_id}/start")
            challenge_id = get_response_data(start)["challenge"]["challenge_id"]

            await client.post(
                f"/api/v1/challenge/{challenge_id}/submit",
                json={"user_answer": "A", "time_taken_seconds": 15, "time_limit_seconds": 60}
            )

            response = await client.get(f"/api/v1/room/{room_id}/leaderboard")
        entries = get_response_data(response)["entries"]
        assert len(entries) == 1
        assert entries[0]["user_id"] == TEST_USER["sub"]
        assert entries[0]["rank"] == 1

    async def test_entry_has_expected_fields(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            create = await client.post("/api/v1/room", json=CREATE_PAYLOAD)
            room_id = get_response_data(create)["room_id"]
            start = await client.post(f"/api/v1/room/{room_id}/start")
            cid = get_response_data(start)["challenge"]["challenge_id"]

            await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )

            entry = (await client.get(f"/api/v1/room/{room_id}/leaderboard")).json()["result"]["entries"][0]
        for field in ("rank", "user_id", "username", "is_correct", "xp_earned", "time_taken_seconds"):
            assert field in entry

    async def test_returns_404_for_nonexistent_room(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/room/does-not-exist/leaderboard")
        assert_error(response, ErrorEnum.ROOM_NOT_FOUND, 404)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.get("/api/v1/room/any-id/leaderboard")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)
