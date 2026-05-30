"""
GiggleAuthProvider — integration stub for Giggle Academy's auth system.

HOW TO INTEGRATE
----------------
Set AUTH_PROVIDER=giggle in your environment. Then implement each method below
by calling your own auth backend. Each method documents exactly what it must
accept, return, and raise.

The contract:
  - decode_token     : JWT decode only — must return a dict with at least {"sub": <user_id>}.
                       Return None on any decode failure (expired, bad signature, etc.).
  - validate_session : Live session check — return True if the token is still valid
                       on your auth server. Return False on any error.
  - sign_in          : Return {"access_token": str, "refresh_token": str} on success.
                       Raise on invalid credentials.
  - sign_up          : Same return shape as sign_in. Raise on duplicate email or
                       policy violations.
  - refresh_token    : Accept a refresh token, return new {"access_token", "refresh_token"}.
                       Raise if the refresh token is expired or invalid.
  - revoke_token     : Invalidate the session server-side. Swallow errors silently
                       (best-effort logout — do not raise).
  - send_reset_password_email : Trigger the reset flow on your auth backend.
                       No return value. Log errors; do not raise.
  - update_user_password : Apply the new password. Raise on invalid token/code.

None of these methods should import or reference Supabase or Cognito — they are
intentionally blank so your team can implement them against any auth backend.
"""

from app.core.authentication_provider import AuthProvider
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest


class GiggleAuthProvider(AuthProvider):
    """
    Stub implementation — all methods raise NotImplementedError.
    Replace each method body with your auth backend calls.
    See module docstring for the full contract.
    """

    def decode_token(self, token: str) -> dict:
        """
        Decode and verify the JWT locally (no network call).
        Return a dict with at least {"sub": <user_id_string>} on success.
        Return None on any failure — do not raise.

        Implement using your JWT library with your signing key/JWKS endpoint.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.decode_token is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def validate_session(self, token: str) -> bool:
        """
        Confirm the token is still active on your auth server (network call).
        Return True if valid, False on any error or expired session.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.validate_session is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def sign_in(self, email: str, password: str) -> dict:
        """
        Authenticate with email + password.
        Return {"access_token": str, "refresh_token": str} on success.
        Raise on invalid credentials.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.sign_in is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def sign_up(self, email: str, password: str) -> dict:
        """
        Register a new user and return a live session.
        Return {"access_token": str, "refresh_token": str} on success.
        Raise on duplicate email or policy violations.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.sign_up is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def refresh_token(self, refresh_token: str) -> dict:
        """
        Exchange a refresh token for a new session.
        Return {"access_token": str, "refresh_token": str}.
        Raise if the refresh token is expired or invalid.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.refresh_token is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def revoke_token(self, token: str) -> None:
        """
        Invalidate the session server-side (logout).
        Best-effort: swallow all errors, do not raise.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.revoke_token is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def send_reset_password_email(self, request: ResetPasswordRequest, origin: str) -> None:
        """
        Trigger the password reset flow for request.email.
        No return value. Log errors; do not raise.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.send_reset_password_email is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )

    async def update_user_password(self, request: UpdatePasswordRequest) -> None:
        """
        Apply the new password using the reset token/code from the email link.
        Raise ValueError if the required token/code is missing.
        Raise on invalid or expired token/code.
        """
        raise NotImplementedError(
            "GiggleAuthProvider.update_user_password is not implemented. "
            "See app/core/authentication/giggle.py for the integration contract."
        )
