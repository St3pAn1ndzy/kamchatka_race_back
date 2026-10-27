"""Публичный API v1.

Префикс: /api/v1

Структура повторяет карту экранов из брифа. По мере готовности
роутеры подключаются сюда. Сейчас - каркас с комментариями.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    content,
    directory,
    map,
    news,
    notifications,
    participants,
    results,
    schedule,
    stages,
    viewer_locations,
    pages,
)

api_router = APIRouter(prefix="/api/v1", tags=["v1"])

api_router.include_router(auth.router)
api_router.include_router(content.router)
api_router.include_router(news.router)
api_router.include_router(results.router)
api_router.include_router(schedule.router)
api_router.include_router(participants.router)
api_router.include_router(map.router)
api_router.include_router(notifications.router)
api_router.include_router(directory.router)
api_router.include_router(stages.router)
api_router.include_router(viewer_locations.router)
api_router.include_router(pages.router)
