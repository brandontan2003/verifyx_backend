"""
Scope enforcement

Usage on any router decorator:

    from app.core.scope.dependencies import require_scope
    from app.enums.ScopeEnum import Scope

    @router.post(
        "/challenge",
        dependencies=[Depends(require_scope(Scope.CHALLENGE_WRITE))]
    )

How it works:
    require_scope(scope) is a factory that returns a FastAPI dependency.
    The dependency:
      1. Extracts the current user from the cookie JWT (via get_current_user)
      2. Loads the user's role_id from the DB
      3. Fetches all scopes for that role (one joined query)
      4. Raises 403 ScopeForbiddenException if the required scope is absent

"""
from typing import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import ScopeForbiddenException, UserNotFoundException
from app.dependencies import get_current_user, get_db
from app.enums.ScopeEnum import ScopeType
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository


def require_scope(*scopes: ScopeType) -> Callable:
    """
    Factory — returns a FastAPI dependency enforcing the given scope.
    Place in the `dependencies` list on any router decorator.
    """

    async def _check_scope(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        user_repo = UserRepository(db)
        role_repo = RoleRepository(db)

        db_user = await user_repo.get_by_user_id(user["sub"])
        if not db_user:
            raise UserNotFoundException()

        # Single joined query — all scopes for this role
        scopes_list = await role_repo.get_user_scopes(db_user.role_id)
        user_scopes = [s.value for s in scopes_list]

        if not any(scope.value in user_scopes for scope in scopes):
            raise ScopeForbiddenException()

    return _check_scope
