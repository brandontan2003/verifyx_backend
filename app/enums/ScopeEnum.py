import enum


class ScopeType(enum.Enum):
    """
    All scopes in the system.
    These are seeded into the DB on first run via the migration.
    Use these constants everywhere — never raw strings.
    """
    # Challenge
    CHALLENGE_READ = "challenge:read"
    CHALLENGE_WRITE = "challenge:write"

    # Room
    ROOM_READ = "room:read"
    ROOM_WRITE = "room:write"

    # Progress
    PROGRESS_READ = "progress:read"
    PROGRESS_WRITE = "progress:write"

    # Leaderboard
    LEADERBOARD_READ = "leaderboard:read"

    # Leaderboard
    USER_READ = "user:read"
    USER_WRITE = "user:write"

    # Admin
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"

    # System
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
