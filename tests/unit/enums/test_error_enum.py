from app.enums.ErrorEnum import ErrorEnum


class TestErrorEnum:
    def test_error_code_returns_first_tuple_element(self):
        assert ErrorEnum.USER_NOT_FOUND.error_code == "USER_NOT_FOUND"
        assert ErrorEnum.RATE_LIMIT_EXCEEDED.error_code == "RATE_LIMIT_EXCEEDED"
        assert ErrorEnum.INVALID_TOKEN.error_code == "INVALID_TOKEN"

    def test_error_message_returns_second_tuple_element(self):
        assert ErrorEnum.USER_NOT_FOUND.error_message == "User not found."
        assert ErrorEnum.RATE_LIMIT_EXCEEDED.error_message == "Too many requests. Please slow down and try again."
        assert ErrorEnum.INVALID_TOKEN.error_message == "Your session has expired. Please log in again."

    def test_error_code_and_message_are_strings(self):
        for member in ErrorEnum:
            assert isinstance(member.error_code, str)
            assert isinstance(member.error_message, str)

    def test_all_error_codes_are_unique(self):
        codes = [m.error_code for m in ErrorEnum]
        assert len(codes) == len(set(codes)), "Duplicate error codes detected"

    def test_all_error_messages_are_non_empty(self):
        for member in ErrorEnum:
            assert member.error_message.strip(), f"{member.name} has empty error_message"

    def test_all_error_codes_are_non_empty(self):
        for member in ErrorEnum:
            assert member.error_code.strip(), f"{member.name} has empty error_code"

    def test_specific_http_status_mappings(self):
        """Key members have expected codes for error shape checking."""
        assert ErrorEnum.VALIDATION_ERROR.error_code == "VALIDATION_ERROR"
        assert ErrorEnum.INTERNAL_SERVER_ERROR.error_code == "INTERNAL_SERVER_ERROR"
        assert ErrorEnum.FORBIDDEN.error_code == "FORBIDDEN"
        assert ErrorEnum.NOT_FOUND.error_code == "NOT_FOUND"
        assert ErrorEnum.METHOD_NOT_ALLOWED.error_code == "METHOD_NOT_ALLOWED"

    def test_domain_error_codes_present(self):
        expected_codes = {
            "CHALLENGE_NOT_FOUND", "ROOM_NOT_FOUND", "ROOM_FULL",
            "ROOM_ALREADY_ACTIVE", "NOT_ROOM_HOST", "ROOM_NOT_ACTIVE",
            "REPORT_NOT_FOUND", "REPORT_TERMINAL_STATE",
            "NEWS_POST_NOT_FOUND", "COMMENT_NOT_FOUND", "COMMENT_DEPTH_EXCEEDED",
            "DAILY_CHALLENGE_LIMIT", "INVALID_ANSWER_FORMAT",
            "SCOPE_FORBIDDEN", "ROLE_FORBIDDEN", "RULES_EXECUTION_FAILURE",
            "BADGE_NOT_FOUND",
        }
        actual_codes = {m.error_code for m in ErrorEnum}
        assert expected_codes.issubset(actual_codes)

    def test_password_reset_failed_present(self):
        assert ErrorEnum.PASSWORD_RESET_FAILED.error_code == "PASSWORD_RESET_FAILED"
        assert "password" in ErrorEnum.PASSWORD_RESET_FAILED.error_message.lower()

    def test_daily_challenge_limit_message_is_friendly(self):
        msg = ErrorEnum.DAILY_CHALLENGE_LIMIT.error_message
        assert "daily" in msg.lower() or "limit" in msg.lower()
