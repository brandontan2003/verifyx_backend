from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, RoleChecker
from app.dto.base import DataResponse
from app.dto.error import ErrorResponse
from app.dto.progress import CreateBadgeRequest, \
    AdminBadgeResponse, UpdateBadgeRequest, RetrieveAllBadgesResponse
from app.enums.ErrorEnum import ErrorEnum
from app.enums.RoleEnum import RoleType
from app.services.badges_service import retrieve_all_badges, create_new_badge, update_badge

router = APIRouter(prefix="/badges", tags=["badges"])


@router.get("/internal", response_model=DataResponse[RetrieveAllBadgesResponse],
            dependencies=[Depends(RoleChecker([RoleType.ADMIN]))],
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def get_all_badges(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await retrieve_all_badges(db)
    return DataResponse(result=result)


@router.post("/internal", response_model=DataResponse[AdminBadgeResponse],
             dependencies=[Depends(RoleChecker([RoleType.ADMIN]))],
             responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                        422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def create_badges(payload: CreateBadgeRequest, user=Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    result = await create_new_badge(payload, db)
    return DataResponse(result=result)


@router.put("/internal/{badge_id}", response_model=DataResponse[AdminBadgeResponse],
            dependencies=[Depends(RoleChecker([RoleType.ADMIN]))],
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       404: {"model": ErrorResponse, "description": ErrorEnum.BADGE_NOT_FOUND.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def update_badges(badge_id: str, payload: UpdateBadgeRequest, user=Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    result = await update_badge(badge_id, payload, db)
    return DataResponse(result=result)
