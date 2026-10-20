"""Сервис кэширования Redis.

Все вызовы Redis обёрнуты в try/except. Если Redis недоступен,
сервис молча возвращает None, а приложение идёт в БД.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings


class CacheService:
    """Асинхронный сервис кэширования с graceful degradation."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None
        self._connected: bool = False

    async def _get_client(self) -> aioredis.Redis | None:
        """Ленивое подключение к Redis. None при ошибке."""
        if not self._connected:
            try:
                settings = get_settings()
                self._client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._client.ping()
                self._connected = True
            except Exception:
                self._client = None
                self._connected = False
                return None
        return self._client

    async def get(self, key: str) -> Any | None:
        """Получить значение по ключу.

        Returns:
            Десериализованное значение или None (промах кэша / ошибка Redis).
        """
        try:
            client = await self._get_client()
            if client is None:
                return None
            val = await client.get(key)
            if val is None:
                return None
            return json.loads(val)
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Записать значение с TTL (сек).

        Объекты сериализуются через json.dumps с default=str,
        что покрывает datetime, Decimal и т.д.
        """
        try:
            client = await self._get_client()
            if client is None:
                return
            await client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:
            pass

    async def delete(self, key: str) -> None:
        """Удалить один ключ."""
        try:
            client = await self._get_client()
            if client is None:
                return
            await client.delete(key)
        except Exception:
            pass

    async def invalidate_pattern(self, pattern: str) -> None:
        """Удалить все ключи, подходящие под glob-паттерн.

        Примеры:
            cache.invalidate_pattern("public:results:*")
            cache.invalidate_pattern("public:stages:*")
        """
        try:
            client = await self._get_client()
            if client is None:
                return
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
        except Exception:
            pass

    async def close(self) -> None:
        """Закрыть соединение с Redis (при завершении работы)."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            finally:
                self._client = None
                self._connected = False


# Сиглтон — один экземпляр на всё приложение.
cache = CacheService()
