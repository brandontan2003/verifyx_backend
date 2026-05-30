import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# picks ENV from system environment, defaults to "dev"
env = os.getenv("ENV", "dev")


class Settings(BaseSettings):
    ENV: str = "dev"

    DATABASE_URL: str = ""
    FRONTEND_URL: str = ""

    # Create a property to use in your code
    @property
    def FRONTEND_URL_LIST(self) -> List[str]:
        urls = [item.strip() for item in self.FRONTEND_URL.split(",") if item.strip()]
        return urls if urls else [""]

    RESET_PASSWORD_ENDPOINT: str = ""

    # Rate Limit
    REDIS_URL: str = ""
    RATE_LIMIT_AI: int = 0
    RATE_LIMIT_AUTH: int = 0
    RATE_LIMIT_ROOM: int = 0
    RATE_LIMIT_READ: int = 0
    RATE_LIMIT_SUBMIT: int = 0
    DAILY_CHALLENGE_LIMIT: int = 1

    # JWT Authentication
    JWT_SIGNING_KEY: str = ""
    JWT_AUDIENCE: str = "authenticated"
    AUTH_PROVIDER: str = "supabase"

    # AI provider selection
    AI_PROVIDER: str = "claude"
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Supabase admin (server-side session revocation)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Cognito (server-side token revocation)
    COGNITO_REGION: str = ""
    COGNITO_CLIENT_ID: str = ""
    COGNITO_USER_POOL_ID: str = ""

    # Rules / Scoring Engine
    # "default" → DefaultScoringEngine (pure-Python, no external dependency)
    # "kie" → KIEScoringEngine (delegates to KIE/Drools DMN server, falls back to DefaultScoringEngine on KIE failure)
    SCORING_ENGINE: str = "default"
    RULE_SERVER_URL: str = ""
    RULE_SERVER_USER: str = ""
    RULE_SERVER_PASSWORD: str = ""
    XP_TABLE: str = "{1: 10, 2: 20, 3: 35, 4: 50, 5: 75}"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / f".env.{env}",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
