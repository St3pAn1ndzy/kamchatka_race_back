"""Публичный health-check для мониторинга и клиентов."""

import datetime as dt

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Пульс API")
async def health() -> dict:
    return {
        "status": "ok",
        "time": dt.datetime.now(dt.UTC).isoformat(),
    }
