import boto3
from botocore.exceptions import ClientError
from jose import jwt, JWTError

from app.config import settings
from app.core.authentication_provider import AuthProvider
from app.core.logger import logger
from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest


class CognitoAuthProvider(AuthProvider):

    def _client(self):
        return boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                settings.JWT_SIGNING_KEY,
                algorithms=["RS256"],
                audience=settings.JWT_AUDIENCE
            )
        except JWTError as ex:
            logger.error("JWT decode error: %s", ex, exc_info=True)
            return None

    async def validate_session(self, token: str) -> bool:
        try:
            self._client().get_user(AccessToken=token)
            return True
        except ClientError as ex:
            logger.error("Cognito session validation error: %s", ex, exc_info=True)
            return False

    async def sign_in(self, email: str, password: str) -> dict:
        try:
            response = self._client().initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": email, "PASSWORD": password},
                ClientId=settings.COGNITO_CLIENT_ID
            )
            result = response["AuthenticationResult"]
            return {
                "access_token": result["AccessToken"],
                "refresh_token": result["RefreshToken"],
            }
        except ClientError as ex:
            logger.error("Cognito sign in error: %s", ex, exc_info=True)
            raise

    async def sign_up(self, email: str, password: str) -> dict:
        try:
            self._client().sign_up(
                ClientId=settings.COGNITO_CLIENT_ID,
                Username=email,
                Password=password,
                UserAttributes=[{"Name": "email", "Value": email}]
            )
            # Auto confirm and sign in — no email verification required
            self._client().admin_confirm_sign_up(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=email
            )
            return await self.sign_in(email, password)
        except ClientError as ex:
            logger.error("Cognito sign up error: %s", ex, exc_info=True)
            raise

    async def refresh_token(self, refresh_token: str) -> dict:
        try:
            response = self._client().initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={"REFRESH_TOKEN": refresh_token},
                ClientId=settings.COGNITO_CLIENT_ID
            )
            result = response["AuthenticationResult"]
            return {
                "access_token": result["AccessToken"],
                "refresh_token": refresh_token,  # Cognito doesn't rotate refresh tokens
            }
        except ClientError as ex:
            logger.error("Cognito refresh token error: %s", ex, exc_info=True)
            raise

    async def revoke_token(self, token: str) -> None:
        try:
            self._client().revoke_token(
                Token=token,
                ClientId=settings.COGNITO_CLIENT_ID
            )
        except Exception as ex:
            logger.error("Failed to revoke Cognito token: %s", ex, exc_info=True)

    async def send_reset_password_email(self, request: ResetPasswordRequest, origin: str) -> None:
        try:
            self._client().forgot_password(
                Username=request.email,
                ClientId=settings.COGNITO_CLIENT_ID
            )
        except Exception as ex:
            logger.error("Failed to send reset password email: %s", ex, exc_info=True)

    async def update_user_password(self, request: UpdatePasswordRequest) -> None:
        """
        Cognito password reset requires the email and the confirmation code
        from the reset email. Both must be forwarded from the frontend form.
        """
        if not request.confirmation_code:
            raise ValueError("Enter the confirmation code from the reset email.")

        try:
            self._client().confirm_forgot_password(
                Username=request.email,
                ConfirmationCode=request.confirmation_code,
                Password=request.password,
                ClientId=settings.COGNITO_CLIENT_ID
            )
        except ClientError as ex:
            error_code = ex.response["Error"]["Code"]
            logger.error("Cognito confirm_forgot_password failed [%s]: %s", error_code, ex, exc_info=True)
            raise
        except Exception as ex:
            logger.error("Failed to update password via Cognito: %s", ex, exc_info=True)
            raise
