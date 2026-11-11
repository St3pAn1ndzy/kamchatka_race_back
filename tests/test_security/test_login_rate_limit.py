"""Проверки защиты входа от перебора паролей через общий Redis"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.security.login_rate_limit import (
    AdminLoginRateLimiter,
    LoginRateLimitMiddleware,
)


@pytest.fixture
async def limiter(test_settings):
    """Выделяет счётчик в разрешённой тестовой Redis DB и закрывает соединение"""
    backend = Redis.from_url(test_settings.REDIS_URL, decode_responses=True)
    instance = AdminLoginRateLimiter(backend, max_attempts=2, window_seconds=60)
    try:
        yield instance, backend
    finally:
        await instance.close()


def _app(limiter):
    app = FastAPI()
    app.add_middleware(LoginRateLimitMiddleware, limiter=limiter)

    @app.post("/api/v1/admin/auth/login")
    @app.post("/admin-panel/login")
    def login():
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Неверный логин или пароль"}, status_code=401)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


async def test_concurrent_workers_share_one_limit(limiter, test_settings):
    """Два экземпляра защиты атомарно разрешают ровно две из двадцати попыток"""
    first, _ = limiter
    second = AdminLoginRateLimiter(
        Redis.from_url(test_settings.REDIS_URL, decode_responses=True),
        max_attempts=2,
        window_seconds=60,
    )
    try:
        decisions = await asyncio.gather(
            *((first if i % 2 else second).check("203.0.113.9") for i in range(20))
        )
    finally:
        await second.close()

    assert sum(decision.allowed for decision in decisions) == 2
    assert all(1 <= decision.retry_after <= 60 for decision in decisions)


async def test_blocked_attempts_do_not_extend_window(limiter):
    """Отказы не продлевают блокировку, а истечение ключа открывает новое окно"""
    instance, backend = limiter
    await instance.check("203.0.113.10")
    await instance.check("203.0.113.10")
    keys = await backend.keys("security:admin-login:*")
    assert len(keys) == 1
    assert "203.0.113.10" not in keys[0]
    ttl_before = await backend.pttl(keys[0])

    assert not (await instance.check("203.0.113.10")).allowed
    assert 0 < await backend.pttl(keys[0]) <= ttl_before

    await backend.pexpire(keys[0], 0)
    assert (await instance.check("203.0.113.10")).allowed


async def test_api_and_panel_share_limit_and_ignore_forged_forwarded_headers(limiter):
    """Смена формы входа или поддельного proxy-заголовка не обходит общий лимит"""
    instance, _ = limiter
    transport = ASGITransport(app=_app(instance), client=("203.0.113.11", 1234))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/v1/admin/auth/login")).status_code == 401
        assert (await client.post("/admin-panel/login")).status_code == 401
        response = await client.post(
            "/api/v1/admin/auth/login", headers={"X-Forwarded-For": "198.51.100.1"}
        )
        assert response.status_code == 429
        assert 1 <= int(response.headers["Retry-After"]) <= 60
        assert "попыток" in response.json()["detail"]
        assert (await client.get("/health")).status_code == 200


async def test_other_client_address_has_independent_limit(limiter):
    """Исчерпанный лимит одного IP не блокирует вход с другого адреса"""
    instance, _ = limiter
    await instance.check("203.0.113.12")
    await instance.check("203.0.113.12")

    assert not (await instance.check("203.0.113.12")).allowed
    assert (await instance.check("203.0.113.13")).allowed


async def test_redis_failure_closes_login_without_calling_password_check():
    """Сбой Redis возвращает 503 до проверки пароля и создания сессии"""
    backend = AsyncMock()
    backend.eval.side_effect = RedisConnectionError("Redis недоступен")
    limiter = AdminLoginRateLimiter(backend, max_attempts=2, window_seconds=60)
    app = _app(limiter)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin-panel/login")
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
        assert (await client.get("/health")).status_code == 200
    backend.eval.assert_awaited_once()


async def test_non_login_requests_do_not_touch_redis():
    """Обычные запросы не обращаются к счётчику и работают при сбое Redis"""
    backend = AsyncMock()
    limiter = AdminLoginRateLimiter(backend, max_attempts=2, window_seconds=60)
    async with AsyncClient(
        transport=ASGITransport(app=_app(limiter)), base_url="http://test"
    ) as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/api/v1/admin/auth/login")).status_code == 405
    backend.eval.assert_not_awaited()


async def test_real_application_limits_before_password_authentication(client, app, monkeypatch):
    """Настоящий роутер FastAPI подключён к защите и не проверяет заблокированный пароль"""
    authenticate = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.admin.auth.authenticate_admin_by_password", authenticate)
    limiter = app.state.admin_login_limiter
    monkeypatch.setattr(limiter, "max_attempts", 2)
    try:
        responses = [
            await client.post(
                "/api/v1/admin/auth/login", json={"login": "admin", "password": "wrong"}
            )
            for _ in range(3)
        ]
        assert [response.status_code for response in responses] == [401, 401, 429]
        assert authenticate.await_count == 2
    finally:
        await limiter.close()
