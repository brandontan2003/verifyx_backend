import httpx
from jose import jwt, JWTError
from supabase import create_client

from app.config import settings
from app.core.logger import logger
from app.core.security import AuthProvider
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest


class SupabaseAuthProvider(AuthProvider):

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                settings.JWT_SIGNING_KEY,
                algorithms=["RS256", "ES256"],
                audience=settings.JWT_AUDIENCE
            )
        except JWTError as ex:
            logger.error("JWT decode error: %s", ex, exc_info=True)
            return None

    async def validate_session(self, token: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.SUPABASE_URL}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": settings.SUPABASE_SERVICE_KEY
                    },
                    timeout=5
                )
                return response.status_code == 200
        except Exception as ex:
            logger.error("Supabase session validation error: %s", ex, exc_info=True)
            return False

    async def sign_in(self, email: str, password: str) -> dict:
        try:
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            response = client.auth.sign_in_with_password({"email": email, "password": password})
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }
        except Exception as ex:
            logger.error("Supabase sign in error: %s", ex, exc_info=True)
            raise

    async def sign_up(self, email: str, password: str) -> dict:
        try:
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            response = client.auth.sign_up({"email": email, "password": password})
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }
        except Exception as ex:
            logger.error("Supabase sign up error: %s", ex, exc_info=True)
            raise

    async def refresh_token(self, refresh_token: str) -> dict:
        try:
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            response = client.auth.refresh_session(refresh_token)
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }
        except Exception as ex:
            logger.error("Supabase refresh token error: %s", ex, exc_info=True)
            raise

    async def revoke_token(self, token: str) -> None:
        try:
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            client.auth.admin.sign_out(token)
        except Exception as ex:
            logger.error("Failed to revoke Supabase token: %s", ex, exc_info=True)

    async def send_reset_password_email(self, request: ResetPasswordRequest, origin: str) -> None:
        try:
            redirect_url = origin + settings.RESET_PASSWORD_ENDPOINT

            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            client.auth.reset_password_for_email(request.email, options={"redirect_to": redirect_url})
        except Exception as ex:
            logger.error("Failed to send reset password email: %s", ex, exc_info=True)

    async def update_user_password(self, request: UpdatePasswordRequest) -> None:
        """
        Supabase password reset requires the one-time access_token from the reset
        email link. That token must be used to create a session client (not the
        service-key admin client), which is then authorised to call update_user().

        The token arrives in the reset URL as a query parameter and is forwarded
        by the frontend in the request body as `token`.
        """
        if not request.token:
            raise ValueError("Supabase password reset requires the token from the reset email link.")

        try:
            # Use the one-time token directly as the Authorization bearer —
            # Supabase's REST PATCH /auth/v1/user honors a valid recovery token.
            async with httpx.AsyncClient() as http:
                response = await http.put(
                    f"{settings.SUPABASE_URL}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {request.token}",
                        "apikey": settings.SUPABASE_SERVICE_KEY,
                        "Content-Type": "application/json",
                    },
                    json={"password": request.password},
                    timeout=10,
                )

            if response.status_code not in (200, 204):
                error_body = response.json()
                logger.error("Supabase update_user failed: status=%d body=%s", response.status_code, error_body)
                raise RuntimeError(error_body['msg'])
        except (ValueError, RuntimeError):
            raise
        except Exception as ex:
            logger.error("Failed to update password via Supabase: %s", ex, exc_info=True)
            raise
