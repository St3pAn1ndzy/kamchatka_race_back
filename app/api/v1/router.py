"""Публичный API v1.

Префикс: /api/v1

Структура повторяет карту экранов из брифа. По мере готовности
роутеры подключаются сюда. Сейчас - каркас с комментариями.
"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1", tags=["v1"])

# По мере готовности раскомментировать и подключать:
#
# from app.api.v1 import auth, state, map, participants, results, content, engagement
#
# api_router.include_router(state.router)
# api_router.include_router(auth.router)
# api_router.include_router(map.router)
# api_router.include_router(participants.router)
# api_router.include_router(results.router)
# api_router.include_router(content.router)
# api_router.include_router(engagement.router)
