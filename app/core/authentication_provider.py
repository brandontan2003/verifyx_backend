from abc import ABC, abstractmethod

from app.dto.auth import ResetPasswordRequest, UpdatePasswordRequest


class AuthProvider(ABC):
    @abstractmethod
    def decode_token(self, token: str) -> dict:
        ...

    @abstractmethod
    async def validate_session(self, token: str) -> bool:
        ...

    @abstractmethod
    async def sign_in(self, email: str, password: str) -> dict:
        ...

    @abstractmethod
    async def sign_up(self, email: str, password: str) -> dict:
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict:
        ...

    @abstractmethod
    async def revoke_token(self, token: str) -> None:
        ...

    @abstractmethod
    async def send_reset_password_email(self, request: ResetPasswordRequest, origin: str) -> None:
        ...

    @abstractmethod
    async def update_user_password(self, request: UpdatePasswordRequest) -> None:
        ...
