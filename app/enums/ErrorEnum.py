import enum


class ErrorEnum(enum.Enum):
    RATE_LIMIT_EXCEEDED = ("RATE_LIMIT_EXCEEDED", "Too many requests. Please slow down and try again.")
    VALIDATION_ERROR = ("VALIDATION_ERROR", "Validation Error")
    INVALID_TOKEN = ("INVALID_TOKEN", "Your session has expired. Please log in again.")
    INTERNAL_SERVER_ERROR = ("INTERNAL_SERVER_ERROR", "An unexpected error occurred. Please try again later.")
    USER_NOT_FOUND = ("USER_NOT_FOUND", "User not found.")
    BADGE_NOT_FOUND = ("BADGE_NOT_FOUND", "Badge not found.")
    CODE_NOT_FOUND = ("CODE_NOT_FOUND", "Code not found.")
    USER_ALREADY_EXISTS = ("USER_ALREADY_EXISTS", "User already registered.")
    LOGOUT_FAILED = ("LOGOUT_FAILED", "Logout failed. Please try again.")
    INVALID_CREDENTIALS = ("INVALID_CREDENTIALS", "Invalid email or password.")
    SIGNUP_FAILED = ("SIGNUP_FAILED", "Sign up failed. Please try again.")
    NOT_FOUND = ("NOT_FOUND", "NOT FOUND")
    METHOD_NOT_ALLOWED = ("METHOD_NOT_ALLOWED", "METHOD NOT ALLOWED")
    FORBIDDEN = ("FORBIDDEN", "FORBIDDEN")
    HTTP_ERROR = ("HTTP_ERROR", "HTTP ERROR")
    CHALLENGE_NOT_FOUND = ("CHALLENGE_NOT_FOUND", "Challenge not found.")
    CHALLENGE_ALREADY_SUBMITTED = ("CHALLENGE_ALREADY_SUBMITTED", "This challenge has already been submitted.")
    ROOM_NOT_FOUND = ("ROOM_NOT_FOUND", "Room not found.")
    ROOM_FULL = ("ROOM_FULL", "Room is full.")
    ROOM_ALREADY_ACTIVE = ("ROOM_ALREADY_ACTIVE", "Room has already started.")
    NOT_ROOM_HOST = ("NOT_ROOM_HOST", "Only the room host can perform this action.")
    ALREADY_IN_ROOM = ("ALREADY_IN_ROOM", "You are already in this room.")
    ROOM_NOT_ACTIVE = ("ROOM_NOT_ACTIVE", "Room has not started yet.")
    INVALID_ANSWER_FORMAT = ("INVALID_ANSWER_FORMAT", "MCQ answer must be A, B, C, or D.")
    PASSWORD_RESET_FAILED = ("PASSWORD_RESET_FAILED", "Password reset failed. Please try again.")
    SCOPE_FORBIDDEN = ("SCOPE_FORBIDDEN", "You do not have permission to perform this action.")
    ROLE_FORBIDDEN = ("ROLE_FORBIDDEN", "You do not have permission to perform this action.")
    REPORT_NOT_FOUND = ("REPORT_NOT_FOUND", "Report not found.")
    RULES_EXECUTION_FAILURE = ("RULES_EXECUTION_FAILURE", "Rules failed or was not evaluated.")
    DAILY_CHALLENGE_LIMIT = ("DAILY_CHALLENGE_LIMIT", "You've reached your daily challenge limit. Come back tomorrow!")
    NEWS_POST_NOT_FOUND = ("NEWS_POST_NOT_FOUND", "News post not found.")
    COMMENT_NOT_FOUND = ("COMMENT_NOT_FOUND", "Comment not found.")
    COMMENT_DEPTH_EXCEEDED = ("COMMENT_DEPTH_EXCEEDED", "Replies can only be one level deep.")
    REPORT_TERMINAL_STATE = ("REPORT_TERMINAL_STATE", "This report has already been resolved and cannot be modified.")

    @property
    def error_code(self) -> str:
        return self.value[0]

    @property
    def error_message(self) -> str:
        return self.value[1]
