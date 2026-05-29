from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.exceptions import BadgeNotFoundException
from app.dto.progress import CreateBadgeRequest, AdminBadgeResponse, UpdateBadgeRequest, RetrieveAllBadgesResponse
from app.repositories.progress_repo import ProgressRepository


async def build_admin_badge_response(badges: list) -> list[AdminBadgeResponse]:
    return [AdminBadgeResponse(
        badge_id=b.badge_id,
        name=b.name,
        description=b.description,
        badge_type=b.badge_type,
        threshold=b.threshold
    ) for b in badges]


async def retrieve_all_badges(database: AsyncSession) -> RetrieveAllBadgesResponse:
    progress_repo = ProgressRepository(database)
    result = await progress_repo.get_all_badges()
    return RetrieveAllBadgesResponse(
        badges=await build_admin_badge_response(result)
    )


async def create_new_badge(payload: CreateBadgeRequest, database: AsyncSession) -> AdminBadgeResponse:
    progress_repo = ProgressRepository(database)
    result = await progress_repo.create_new_badge(payload.name, payload.description, payload.badge_type,
                                                  payload.threshold)
    return AdminBadgeResponse(
        badge_id=result.badge_id,
        name=result.name,
        description=result.description,
        badge_type=result.badge_type,
        threshold=result.threshold
    )


async def update_badge(badge_id, payload: UpdateBadgeRequest, database: AsyncSession) -> AdminBadgeResponse:
    progress_repo = ProgressRepository(database)

    badge = await progress_repo.retrieve_badge_by_badge_id(badge_id)
    if not badge:
        raise BadgeNotFoundException()

    result = await progress_repo.update_badge(badge_id, payload.name, payload.description)
    return AdminBadgeResponse(
        badge_id=result.badge_id,
        name=result.name,
        description=result.description,
        badge_type=result.badge_type,
        threshold=result.threshold
    )
