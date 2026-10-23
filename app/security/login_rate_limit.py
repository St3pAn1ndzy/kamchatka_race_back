"""Общий для API и админки лимит попыток входа с одного IP"""

import asyncio
import hashlib
import logging
import math
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("avacha.security")

# Проверка, увеличение и установка срока жизни выполняются одной операцией Redis
_RESERVE_ATTEMPT = """
local attempts = tonumber(redis.call('GET', KEYS[1]) or '0')
if attempts >= tonumber(ARGV[1]) then
    return {0, redis.call('PTTL', KEYS[1])}
end
attempts = redis.call('INCR', KEYS[1])
if attempts == 1 then
    redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return {1, redis.call('PTTL', KEYS[1])}
"""


@dataclass(frozen=True)
class LoginLimitDecision:
    """Результат проверки и оставшееся время окна в секундах"""

    allowed: bool
    retry_after: int


class LoginLimitUnavailable(RuntimeError):
    """Общий счётчик недоступен, поэтому безопасно разрешить вход нельзя"""


class AdminLoginRateLimiter:
    """Резервирует попытку до проверки пароля, включая успешные входы"""

    def __init__(self, backend: Redis, *, max_attempts: int, window_seconds: int) -> None:
        if max_attempts < 1 or window_seconds < 1:
            raise ValueError("Лимит попыток и длительность окна должны быть положительными")
        self.backend = backend
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    async def check(self, client_ip: str) -> LoginLimitDecision:
        """Атомарно проверяет общий лимит, не сохраняя IP открытым текстом"""
        key = "security:admin-login:" + hashlib.sha256(client_ip.encode()).hexdigest()
        try:
            async with asyncio.timeout(2):
                allowed, ttl_ms = await self.backend.eval(
                    _RESERVE_ATTEMPT,
                    1,
                    key,
                    self.max_attempts,
                    self.window_seconds * 1000,
                )
        except (RedisError, OSError, TimeoutError) as exc:
            raise LoginLimitUnavailable from exc
        return LoginLimitDecision(
            allowed=bool(allowed), retry_after=max(1, math.ceil(ttl_ms / 1000))
        )

    async def close(self) -> None:
        """Освобождает соединения при остановке процесса FastAPI"""
        await self.backend.aclose()


class LoginRateLimitMiddleware:
    """Ограничивает только POST входа до чтения тела и обращения к БД"""

    _paths = {"/api/v1/admin/auth/login", "/admin-panel/login"}

    def __init__(self, app: ASGIApp, *, limiter: AdminLoginRateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") not in self._paths
        ):
            await self.app(scope, receive, send)
            return

        # Адрес задаёт ASGI-сервер; произвольному X-Forwarded-For здесь не доверяем
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        try:
            decision = await self.limiter.check(client_ip)
        except LoginLimitUnavailable:
            logger.warning("admin_login_limit_unavailable")
            response = JSONResponse(
                {"detail": "Вход временно недоступен. Повторите позже."},
                status_code=503,
                headers={"Retry-After": "5"},
            )
            await response(scope, receive, send)
            return

        if not decision.allowed:
            response = JSONResponse(
                {"detail": "Слишком много попыток входа. Повторите позже."},
                status_code=429,
                headers={"Retry-After": str(decision.retry_after)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
