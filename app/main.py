from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.config import settings
from app.core.exceptions.exceptions import register_exception_handlers
from app.core.rate_limit.redis_store import close_redis, init_redis
from app.database.database import init_engine
from app.dto.base import HealthCheckDTO, SuccessResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine(settings.DATABASE_URL)

    redis = aioredis.from_url(settings.REDIS_URL)
    init_redis(redis)

    await health_check()
    yield
    await close_redis()


app = FastAPI(title="VerifyX API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_URL_LIST,  # exact origin required for cookies
    allow_credentials=True,  # required for httpOnly cookies
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health", response_model=HealthCheckDTO)
async def health_check():
    return SuccessResponse()
