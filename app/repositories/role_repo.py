from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import RoleType, ScopeType, RoleScope, Role, Scope


class RoleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_role_by_name(self, name: str) -> RoleType | None:
        result = await self.db.execute(
            select(RoleType).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def get_role_ids_by_names(self, list_of_roles: list[RoleType]) -> list[Role]:
        result = []
        for role in list_of_roles:
            db_result = await self.db.execute(
                select(Role).where(Role.name == role)
            )
            role_id = db_result.scalar_one_or_none().role_id
            result.append(role_id)
        return result

    async def get_user_scopes(self, role_id: str) -> list[ScopeType]:
        """
        Return all scope names for a given role_id.
        Result is cached in the scope dependency — this query
        runs once per request, not once per scope check.
        """
        result = await self.db.execute(
            select(Scope.name)
            .join(RoleScope, RoleScope.scope_id == Scope.scope_id)
            .where(RoleScope.role_id == role_id)
        )
        return list(result.scalars().all())
