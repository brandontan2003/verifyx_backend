from fastapi import APIRouter

from app.api.v1 import auth, user, progress, room, challenge, leaderboard, code, report, badges, chatbot, news

v1_router = APIRouter()
v1_router.include_router(auth.router)
v1_router.include_router(user.router)
v1_router.include_router(progress.router)
v1_router.include_router(room.router)
v1_router.include_router(challenge.router)
v1_router.include_router(leaderboard.router)
v1_router.include_router(code.router)
v1_router.include_router(report.router)
v1_router.include_router(badges.router)
v1_router.include_router(chatbot.router)
v1_router.include_router(news.router)
