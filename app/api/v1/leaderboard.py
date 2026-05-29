from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit.dependencies import read_rate_limit
from app.dependencies import get_db
from app.dto.base import DataResponse
from app.dto.error import ErrorResponse
from app.dto.leaderboard import LeaderboardResponse
from app.enums.ErrorEnum import ErrorEnum
from app.services.leaderboard_service import retrieve_leaderboard

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=DataResponse[LeaderboardResponse],
            dependencies=[Depends(read_rate_limit)],
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def get_leaderboard(limit: int = Query(default=50, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    result = await retrieve_leaderboard(db, limit)
    return DataResponse(result=result)
