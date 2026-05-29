"""
Integration tests for /api/v1/challenge endpoints.
"""
from app.enums.ChallengeStatusEnum import ChallengeStatus
from app.enums.ErrorEnum import ErrorEnum
from app.enums.QuestionTypeEnum import QuestionType
from app.enums.ThemeEnum import QuestionTheme
from app.models.challenge import Challenge
from tests.conftest import _seed_user, TEST_USER, AppTestClient, assert_error, get_response_data


# Generate Challenge
class TestGenerateChallenge:
    async def test_returns_200_with_challenge(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
        assert response.status_code == 200
        data = get_response_data(response)
        assert "challenge_id" in data
        assert "question" in data
        assert "options" in data

    async def test_correct_option_id_not_in_response(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
        assert "correct_option_id" not in get_response_data(response)

    async def test_model_answer_not_in_response(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
        assert "model_answer" not in get_response_data(response)

    async def test_question_type_is_present(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
        assert get_response_data(response)["question_type"] in ("mcq", "true_false")

    async def test_returns_422_for_missing_theme(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post("/api/v1/challenge", json={})
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_422_for_blank_theme(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/challenge", json={"theme": "   "}
            )
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Retrieve Challenge History
class TestChallengeHistory:
    async def test_returns_empty_when_no_challenges(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/challenge/history")
        assert response.status_code == 200
        data = get_response_data(response)
        assert data["total"] == 0
        assert data["items"] == []

    async def test_returns_challenges_after_generation(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            await client.post("/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION})
            await client.post("/api/v1/challenge", json={"theme": "phishing"})

            response = await client.get("/api/v1/challenge/history")
        data = get_response_data(response)
        assert data["total"] == 2

    async def test_page_size_respected(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            for _ in range(5):
                await client.post("/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION})

            response = await client.get("/api/v1/challenge/history?page=1&page_size=3")
        data = get_response_data(response)
        assert len(data["items"]) == 3
        assert data["total_pages"] == 2

    async def test_total_pages_correct(self, db_session, mock_ai, mock_redis):
        mock_redis._state.force_limit = False

        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            for _ in range(7):
                await client.post("/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION})

            response = await client.get("/api/v1/challenge/history?page=1&page_size=3")
        assert get_response_data(response)["total_pages"] == 3

    async def test_each_item_has_attempts_list(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            gen = await client.post("/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION})
            challenge_id = gen.json()["result"]["challenge_id"]
            await client.post(
                f"/api/v1/challenge/{challenge_id}/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )

            response = await client.get("/api/v1/challenge/history")
        items = get_response_data(response)["items"]
        assert len(items[0]["attempts"]) == 1

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.get("/api/v1/challenge/history")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Retrieve Challenge By ChallengeId
class TestGetChallenge:
    async def test_returns_200_for_own_challenge(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            gen = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
            challenge_id = gen.json()["result"]["challenge_id"]

            response = await client.get(f"/api/v1/challenge/{challenge_id}")

        assert response.status_code == 200
        assert get_response_data(response)["challenge_id"] == challenge_id

    async def test_correct_option_id_not_in_get_response(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            gen = await client.post(
                "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
            )
            challenge_id = get_response_data(gen)["challenge_id"]

            response = await client.get(f"/api/v1/challenge/{challenge_id}")
        assert "correct_option_id" not in get_response_data(response)

    async def test_returns_404_for_nonexistent_challenge(self, db_session):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/challenge/does-not-exist")
        assert_error(response, ErrorEnum.CHALLENGE_NOT_FOUND, 404)

    async def test_returns_404_for_other_users_challenge(self, db_session):
        """Challenge owned by another user must return 404 — not 403."""

        await _seed_user(db_session)

        other_challenge = Challenge(
            challenge_id="ch-other-user",
            user_id="other-user-uid-9999",
            theme="phishing", difficulty=1,
            question_type=QuestionType.mcq,
            title="Other user challenge",
            content="content", question="question?",
            options=[{"id": "A", "text": "x"}, {"id": "B", "text": "y"},
                     {"id": "C", "text": "z"}, {"id": "D", "text": "w"}],
            correct_option_id="A", tags=[],
            status=ChallengeStatus.pending,
        )
        db_session.add(other_challenge)
        await db_session.commit()
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.get("/api/v1/challenge/ch-other-user")
        assert_error(response, ErrorEnum.CHALLENGE_NOT_FOUND, 404)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.get("/api/v1/challenge/any-id")
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)


# Submit Answer
async def _generate(client):
    """Helper — generate a challenge and return its ID."""
    res = await client.post(
        "/api/v1/challenge", json={"theme": QuestionTheme.MISINFORMATION}
    )
    assert res.status_code == 200, res.json()

    data = get_response_data(res)
    assert "challenge_id" in data, data
    return data["challenge_id"]


class TestSubmitAnswer:

    async def test_returns_200_with_result_and_debrief(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)

            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert response.status_code == 200
        data = get_response_data(response)
        assert "is_correct" in data
        assert "debrief" in data
        assert "correct_answer_display" in data

    async def test_correct_option_id_revealed_in_submit_response(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        data = get_response_data(response)
        assert "correct_answer_display" in data
        assert data["correct_answer_display"] != ""

    async def test_debrief_has_required_fields(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        debrief = get_response_data(response)["debrief"]
        assert "summary" in debrief
        assert "key_lesson" in debrief
        assert "red_flags" in debrief
        assert "tip" in debrief

    async def test_xp_earned_on_first_correct(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A", "time_taken_seconds": 5, "time_limit_seconds": 60}
            )
        assert get_response_data(response)["xp_earned"] > 0

    async def test_zero_xp_on_subsequent_correct(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            submit = {"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}

            await client.post(f"/api/v1/challenge/{cid}/submit", json=submit)
            response = await client.post(f"/api/v1/challenge/{cid}/submit", json=submit)
        assert get_response_data(response)["xp_earned"] == 0

    async def test_attempt_number_increments(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            submit = {"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}

            actual_response_1 = await client.post(f"/api/v1/challenge/{cid}/submit", json=submit)
            actual_response_2 = await client.post(f"/api/v1/challenge/{cid}/submit", json=submit)
        first_response = get_response_data(actual_response_1)
        second_response = get_response_data(actual_response_2)
        assert first_response["attempt_number"] == 1
        assert second_response["attempt_number"] == 2

    async def test_returns_422_for_invalid_option_c_on_true_false(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "C", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.INVALID_ANSWER_FORMAT, 422)

    async def test_returns_422_for_option_z(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "Z", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.INVALID_ANSWER_FORMAT, 422)

    async def test_returns_422_for_missing_time_fields(self, db_session, mock_ai):
        await _seed_user(db_session)

        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            cid = await _generate(client)
            response = await client.post(
                f"/api/v1/challenge/{cid}/submit",
                json={"user_answer": "A"}
            )
        assert_error(response, ErrorEnum.VALIDATION_ERROR, 422)

    async def test_returns_404_for_nonexistent_challenge(self, db_session, mock_ai):
        await _seed_user(db_session)
        async with AppTestClient(db_session, auth_user=TEST_USER) as client:
            response = await client.post(
                "/api/v1/challenge/does-not-exist/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.CHALLENGE_NOT_FOUND, 404)

    async def test_returns_401_when_unauthenticated(self, db_session):
        async with AppTestClient(db_session) as client:
            response = await client.post(
                "/api/v1/challenge/any-id/submit",
                json={"user_answer": "A", "time_taken_seconds": 10, "time_limit_seconds": 60}
            )
        assert_error(response, ErrorEnum.INVALID_TOKEN, 401)
