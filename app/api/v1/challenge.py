from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit.dependencies import ai_rate_limit, read_rate_limit
from app.core.scope.dependencies import require_scope
from app.dependencies import get_current_user, get_db
from app.dto.base import DataResponse
from app.dto.challenge import (
    GenerateChallengeRequest, ChallengeResponse,
    SubmitAnswerRequest, AttemptResponse,
    ChallengeHistoryResponse,
)
from app.dto.error import ErrorResponse
from app.enums.ErrorEnum import ErrorEnum
from app.enums.ScopeEnum import ScopeType
from app.services.challenge_service import (
    generate_challenge, get_challenge, get_challenge_history, submit_answer
)

router = APIRouter(prefix="/challenge", tags=["challenge"])


@router.post("", response_model=DataResponse[ChallengeResponse],
             dependencies=[Depends(ai_rate_limit), Depends(require_scope(ScopeType.CHALLENGE_WRITE))],
             summary="Generate a new challenge — type (MCQ/free-text) and difficulty set by Claude",
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def create_challenge(payload: GenerateChallengeRequest, user=Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    result = await generate_challenge(user["sub"], payload, db)
    return DataResponse(result=result)


@router.get("/history", response_model=DataResponse[ChallengeHistoryResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.CHALLENGE_READ))],
            summary="Paginated challenge history with all attempts per challenge",
            responses={401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                       422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def challenge_history(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                            user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_challenge_history(user["sub"], page, page_size, db)
    return DataResponse(result=result)


@router.get("/{challenge_id}", response_model=DataResponse[ChallengeResponse],
            dependencies=[Depends(read_rate_limit), Depends(require_scope(ScopeType.CHALLENGE_READ))],
            summary="Fetch a challenge by ID (safe to call after page refresh)",
            responses={
                401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                404: {"model": ErrorResponse, "description": ErrorEnum.CHALLENGE_NOT_FOUND.error_code},
                422: {"model": ErrorResponse, "description": ErrorEnum.VALIDATION_ERROR.error_code}})
async def retrieve_challenge(challenge_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_challenge(user["sub"], challenge_id, db)
    return DataResponse(result=result)


@router.post("/{challenge_id}/submit", response_model=DataResponse[AttemptResponse],
             dependencies=[Depends(ai_rate_limit), Depends(require_scope(ScopeType.CHALLENGE_WRITE))],
             summary="Submit an attempt — multiple attempts allowed, XP awarded on first correct only",
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 404: {"model": ErrorResponse, "description": ErrorEnum.CHALLENGE_NOT_FOUND.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.INVALID_ANSWER_FORMAT.error_code}})
async def submit_challenge_answer(challenge_id: str, payload: SubmitAnswerRequest, user=Depends(get_current_user),
                                  db: AsyncSession = Depends(get_db)):
    result = await submit_answer(user["sub"], challenge_id, payload, db)
    return DataResponse(result=result)
