from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.dto.base import DataResponse
from app.dto.error import ErrorResponse
from app.dto.news import (
    NewsFeedResponse,
    NewsPostDetail,
    CommentResponse,
    CreateCommentRequest,
    ReactRequest,
)
from app.enums.ErrorEnum import ErrorEnum
from app.services.news_service import (
    get_news_feed,
    get_news_detail,
    add_comment,
    react_to_post,
)

router = APIRouter(prefix="/news", tags=["News & Discussion"])


@router.get("", response_model=DataResponse[NewsFeedResponse],
            responses={
                401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code}
            })
async def list_news(page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50),
                    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_news_feed(page=page, page_size=page_size, database=db)
    return DataResponse(result=result)


@router.get("/{news_id}", response_model=DataResponse[NewsPostDetail],
            responses={
                401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                404: {"model": ErrorResponse, "description": ErrorEnum.NEWS_POST_NOT_FOUND.error_code},
            })
async def get_news(news_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await get_news_detail(news_id=news_id, user_id=user["sub"], database=db)
    return DataResponse(result=result)


@router.post("/{news_id}/comments", response_model=DataResponse[CommentResponse],
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 404: {"model": ErrorResponse, "description": ErrorEnum.NEWS_POST_NOT_FOUND.error_code},
                 422: {"model": ErrorResponse, "description": ErrorEnum.COMMENT_DEPTH_EXCEEDED.error_code},
             })
async def post_comment(news_id: str, payload: CreateCommentRequest, user=Depends(get_current_user),
                       db: AsyncSession = Depends(get_db), ):
    result = await add_comment(
        news_id=news_id,
        user_id=user["sub"],
        payload=payload,
        database=db,
    )
    return DataResponse(result=result)


@router.post("/{news_id}/react", response_model=DataResponse[NewsPostDetail],
             responses={
                 401: {"model": ErrorResponse, "description": ErrorEnum.INVALID_TOKEN.error_code},
                 404: {"model": ErrorResponse, "description": ErrorEnum.NEWS_POST_NOT_FOUND.error_code},
             })
async def react(news_id: str, payload: ReactRequest, user=Depends(get_current_user),
                db: AsyncSession = Depends(get_db), ):
    result = await react_to_post(
        news_id=news_id,
        user_id=user["sub"],
        payload=payload,
        database=db,
    )
    return DataResponse(result=result)
