"""Публичный API v1.

Префикс: /api/v1

Структура повторяет карту экранов из брифа. По мере готовности
роутеры подключаются сюда. Сейчас - каркас с комментариями.
"""

from fastapi import APIRouter

from app.api.v1 import auth, content, news, participants, schedule, notifications

api_router = APIRouter(prefix="/api/v1", tags=["v1"])

api_router.include_router(auth.router)
api_router.include_router(content.router)
api_router.include_router(news.router)
api_router.include_router(schedule.router)
api_router.include_router(participants.router)
api_router.include_router(notifications.router)
