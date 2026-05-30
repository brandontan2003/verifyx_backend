from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.config import settings
from app.core.cache.cache_store import close_store, init_store
from app.core.cache.registry import RedisStore, InMemoryStore
from app.core.exceptions.exceptions import register_exception_handlers
from app.core.logger import logger
from app.database.database import init_engine
from app.dto.base import HealthCheckDTO, SuccessResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine(settings.DATABASE_URL)
    _init_rate_limit_store()
    await health_check()
    yield
    await close_store()


def _init_rate_limit_store() -> None:
    """
    Select the RateLimitStore implementation based on REDIS_URL.
    """

    if settings.REDIS_URL:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL)
        init_store(RedisStore(client))
        logger.info("RateLimitStore: RedisStore (url=%s)", settings.REDIS_URL)
    else:
        init_store(InMemoryStore())
        logger.warning(
            "RateLimitStore: InMemoryStore — REDIS_URL not set. "
            "Rate limits and daily challenge counters are process-local. "
            "Do not use with multiple workers."
        )


app = FastAPI(title="VerifyX API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_URL_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health", response_model=HealthCheckDTO)
async def health_check():
    return SuccessResponse()
