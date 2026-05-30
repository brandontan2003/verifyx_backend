from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core.exceptions.exceptions import (
    AlreadyInRoomException,
    BadgeNotFoundException,
    BaseAppException,
    ChallengeAlreadySubmittedException,
    ChallengeNotFoundException,
    CommentDepthExceededException,
    CommentNotFoundException,
    DailyChallengeLimitException,
    InvalidAnswerFormatException,
    InvalidCredentialsException,
    InvalidTokenException,
    LogoutFailedException,
    NewsPostNotFoundException,
    NotRoomHostException,
    PasswordResetFailedException,
    RateLimitExceededException,
    ReportNotFoundException,
    ReportTerminalStateException,
    RoleForbiddenException,
    RoomAlreadyActiveException,
    RoomFullException,
    RoomNotActiveException,
    RoomNotFoundException,
    RulesException,
    ScopeForbiddenException,
    SignUpFailedException,
    UserAlreadyExistsException,
    UserNotFoundException,
    register_exception_handlers,
)
from app.enums.ErrorEnum import ErrorEnum


class TestBaseAppException:
    def test_stores_status_code_error_code_and_message(self):
        exc = BaseAppException(400, "BAD_REQUEST", "Something went wrong")
        assert exc.status_code == 400
        assert exc.error_code == "BAD_REQUEST"
        assert exc.error_message == "Something went wrong"

    def test_is_exception_subclass(self):
        exc = BaseAppException(500, "ERR", "msg")
        assert isinstance(exc, Exception)


class TestConcreteExceptions:
    """
    Each exception must carry the exact HTTP status and ErrorEnum values
    so that register_exception_handlers returns the correct response shape.
    """

    def _assert_exc(self, exc, expected_status, expected_code, message_fragment=None):
        assert exc.status_code == expected_status, f"{type(exc).__name__}: expected {expected_status}, got {exc.status_code}"
        assert exc.error_code == expected_code, f"{type(exc).__name__}: expected code {expected_code}, got {exc.error_code}"
        if message_fragment:
            assert message_fragment.lower() in exc.error_message.lower()

    def test_user_already_exists(self):
        self._assert_exc(UserAlreadyExistsException(), 400, ErrorEnum.USER_ALREADY_EXISTS.error_code)

    def test_user_not_found(self):
        self._assert_exc(UserNotFoundException(), 404, ErrorEnum.USER_NOT_FOUND.error_code)

    def test_badge_not_found(self):
        self._assert_exc(BadgeNotFoundException(), 404, ErrorEnum.BADGE_NOT_FOUND.error_code)

    def test_invalid_token(self):
        self._assert_exc(InvalidTokenException(), 401, ErrorEnum.INVALID_TOKEN.error_code)

    def test_logout_failed(self):
        self._assert_exc(LogoutFailedException(), 500, ErrorEnum.LOGOUT_FAILED.error_code)

    def test_invalid_credentials(self):
        self._assert_exc(InvalidCredentialsException(), 401, ErrorEnum.INVALID_CREDENTIALS.error_code)

    def test_signup_failed(self):
        self._assert_exc(SignUpFailedException(), 400, ErrorEnum.SIGNUP_FAILED.error_code)

    def test_challenge_not_found(self):
        self._assert_exc(ChallengeNotFoundException(), 404, ErrorEnum.CHALLENGE_NOT_FOUND.error_code)

    def test_challenge_already_submitted(self):
        self._assert_exc(ChallengeAlreadySubmittedException(), 409, ErrorEnum.CHALLENGE_ALREADY_SUBMITTED.error_code)

    def test_room_not_found(self):
        self._assert_exc(RoomNotFoundException(), 404, ErrorEnum.ROOM_NOT_FOUND.error_code)

    def test_room_full(self):
        self._assert_exc(RoomFullException(), 409, ErrorEnum.ROOM_FULL.error_code)

    def test_room_already_active(self):
        self._assert_exc(RoomAlreadyActiveException(), 409, ErrorEnum.ROOM_ALREADY_ACTIVE.error_code)

    def test_not_room_host(self):
        self._assert_exc(NotRoomHostException(), 403, ErrorEnum.NOT_ROOM_HOST.error_code)

    def test_already_in_room(self):
        self._assert_exc(AlreadyInRoomException(), 409, ErrorEnum.ALREADY_IN_ROOM.error_code)

    def test_room_not_active(self):
        self._assert_exc(RoomNotActiveException(), 409, ErrorEnum.ROOM_NOT_ACTIVE.error_code)

    def test_invalid_answer_format(self):
        self._assert_exc(InvalidAnswerFormatException(), 422, ErrorEnum.INVALID_ANSWER_FORMAT.error_code)

    def test_password_reset_failed_default_message(self):
        exc = PasswordResetFailedException()
        assert exc.status_code == 400
        assert exc.error_code == ErrorEnum.PASSWORD_RESET_FAILED.error_code
        assert exc.error_message == ErrorEnum.PASSWORD_RESET_FAILED.error_message

    def test_password_reset_failed_custom_message(self):
        exc = PasswordResetFailedException(detail="Token expired")
        assert exc.error_message == "Token expired"

    def test_rate_limit_exceeded_default_headers(self):
        exc = RateLimitExceededException()
        assert exc.status_code == 429
        assert exc.error_code == ErrorEnum.RATE_LIMIT_EXCEEDED.error_code
        assert exc.headers == {}

    def test_rate_limit_exceeded_custom_headers(self):
        h = {"Retry-After": "30"}
        exc = RateLimitExceededException(headers=h)
        assert exc.headers == h

    def test_rules_exception_default(self):
        exc = RulesException()
        assert exc.status_code == 500
        assert exc.error_code == ErrorEnum.RULES_EXECUTION_FAILURE.error_code
        assert exc.headers == {}

    def test_rules_exception_custom_headers(self):
        exc = RulesException(headers={"X-Debug": "1"})
        assert exc.headers == {"X-Debug": "1"}

    def test_scope_forbidden(self):
        self._assert_exc(ScopeForbiddenException(), 403, ErrorEnum.SCOPE_FORBIDDEN.error_code)

    def test_role_forbidden(self):
        self._assert_exc(RoleForbiddenException(), 403, ErrorEnum.ROLE_FORBIDDEN.error_code)

    def test_report_not_found(self):
        self._assert_exc(ReportNotFoundException(), 404, ErrorEnum.REPORT_NOT_FOUND.error_code)

    def test_daily_challenge_limit(self):
        self._assert_exc(DailyChallengeLimitException(), 429, ErrorEnum.DAILY_CHALLENGE_LIMIT.error_code)

    def test_news_post_not_found(self):
        self._assert_exc(NewsPostNotFoundException(), 404, ErrorEnum.NEWS_POST_NOT_FOUND.error_code)

    def test_comment_not_found(self):
        self._assert_exc(CommentNotFoundException(), 404, ErrorEnum.COMMENT_NOT_FOUND.error_code)

    def test_comment_depth_exceeded(self):
        self._assert_exc(CommentDepthExceededException(), 422, ErrorEnum.COMMENT_DEPTH_EXCEEDED.error_code)

    def test_report_terminal_state(self):
        self._assert_exc(ReportTerminalStateException(), 409, ErrorEnum.REPORT_TERMINAL_STATE.error_code)


def _make_app_with_route(route_exc=None):
    """Spin up a minimal FastAPI app with exception handlers and one test route."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test")
    async def _route():
        if route_exc:
            raise route_exc
        return {"ok": True}

    return app


class TestRegisterExceptionHandlers:
    def test_starlette_404_returns_error_shape(self):
        app = _make_app_with_route()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/nonexistent")
        assert r.status_code == 404
        body = r.json()
        assert "result" in body
        assert "errors" in body["result"]
        assert body["result"]["errors"][0]["error_code"] == ErrorEnum.NOT_FOUND.error_code

    def test_base_app_exception_propagated_correctly(self):
        app = _make_app_with_route(RoomNotFoundException())
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/test")
        assert r.status_code == 404
        body = r.json()
        assert body["result"]["errors"][0]["error_code"] == ErrorEnum.ROOM_NOT_FOUND.error_code

    def test_403_forbidden_maps_to_forbidden_code(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        app = _make_app_with_route(StarletteHTTPException(status_code=403, detail="nope"))
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/test")
        assert r.status_code == 403
        body = r.json()
        assert body["result"]["errors"][0]["error_code"] == ErrorEnum.FORBIDDEN.error_code

    def test_405_method_not_allowed_maps_correctly(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/only-get")
        async def _only_get():
            return {}

        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/only-get")
        assert r.status_code == 405
        body = r.json()
        assert body["result"]["errors"][0]["error_code"] == ErrorEnum.METHOD_NOT_ALLOWED.error_code

    def test_validation_error_returns_field_details(self):
        from pydantic import BaseModel

        class Payload(BaseModel):
            name: str
            age: int

        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/create")
        async def _create(payload: Payload):
            return payload

        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/create", json={"name": "Alice"})  # missing `age`
        assert r.status_code == 422
        body = r.json()
        errors = body["result"]["errors"]
        assert any(e["error_code"] == "VALIDATION_ERROR" for e in errors)
        assert any("age" in (e.get("field_name") or "") for e in errors)

    def test_unhandled_exception_returns_500(self):
        app = _make_app_with_route(RuntimeError("boom"))
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/test")
        assert r.status_code == 500
        body = r.json()
        assert body["result"]["errors"][0]["error_code"] == ErrorEnum.INTERNAL_SERVER_ERROR.error_code

    def test_error_response_always_has_path(self):
        app = _make_app_with_route(UserNotFoundException())
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/test")
        body = r.json()
        assert body.get("path") == "/test"

    def test_error_response_status_field_is_error(self):
        app = _make_app_with_route(BadgeNotFoundException())
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/test")
        body = r.json()
        assert body["status"] == "ERROR"
