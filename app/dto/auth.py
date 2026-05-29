from typing import Optional

from pydantic import field_validator

from app.dto.base import BaseDTO


class SignInRequest(BaseDTO):
    email: str
    password: str


class SignUpRequest(BaseDTO):
    email: str
    password: str


class TokenResponse(BaseDTO):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ResetPasswordRequest(BaseDTO):
    email: str


class UpdatePasswordRequest(BaseDTO):
    """
    Unified password-reset completion DTO for both providers.

    Supabase flow:
      - User clicks the reset link → lands on /reset-password?token=<access_token>
      - Frontend sends: { password, token }
      - Backend exchanges the token for a session and calls update_user()

    Cognito flow:
      - User receives a 6-digit code by email
      - Frontend sends: { email, password, confirmation_code }
      - Backend calls confirm_forgot_password()

    The frontend reset page always renders the same form.
    It reads `token` from the URL query param (Supabase) and `email` from
    the same URL param (Cognito sends email in the link too).
    Whichever fields are null are simply ignored by the active provider.
    """
    email: str
    password: str
    token: Optional[str] = None  # Supabase: access_token from reset URL
    confirmation_code: Optional[str] = None  # Cognito: 6-digit code from email

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("password must not be blank")
        return v

    @field_validator("email")
    @classmethod
    def email_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("email must not be blank")
        return v
