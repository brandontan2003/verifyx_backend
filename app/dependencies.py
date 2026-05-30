# Auth Guard, DB Session injection
from typing import List

from fastapi import Cookie, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.authentication.cognito import CognitoAuthProvider
from app.core.authentication.supabase import SupabaseAuthProvider
from app.core.authentication_provider import AuthProvider
from app.core.exceptions.exceptions import InvalidTokenException, RoleForbiddenException
from app.database.database import get_sessionmaker
from app.enums.RoleEnum import RoleType
from app.models.user import User
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository

# Keep HTTPBearer for Swagger UI compatibility
security = HTTPBearer(auto_error=False)


def get_auth_provider() -> AuthProvider:
    if settings.AUTH_PROVIDER == "cognito":
        return CognitoAuthProvider()
    return SupabaseAuthProvider()


async def get_db():
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        yield session


# Authentication Dependency (Who you are)
async def get_current_user(access_token: str = Cookie(default=None)):
    if not access_token:
        raise InvalidTokenException()

    provider = get_auth_provider()

    # 1. Validate JWT signature and expiry
    payload = provider.decode_token(access_token)
    if not payload:
        raise InvalidTokenException()

    # 2. Validate session is still active on Supabase/Cognito
    is_active = await provider.validate_session(access_token)
    if not is_active:
        raise InvalidTokenException()

    return payload


async def get_role(user_id: str, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_user_id(user_id)
    return user.role_id


async def get_allowed_role_ids(list_of_roles: List[RoleType], db: AsyncSession = Depends(get_db)):
    role_repo = RoleRepository(db)
    role_ids = await role_repo.get_role_ids_by_names(list_of_roles)
    return role_ids


# Authorization Dependency Class (What you can do)
class RoleChecker:
    def __init__(self, allowed_roles: List[RoleType]):
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        user_role_id = await get_role(current_user["sub"], db)
        allowed_role_ids = await get_allowed_role_ids(self.allowed_roles, db)

        if user_role_id not in allowed_role_ids:
            raise RoleForbiddenException()
        return current_user
