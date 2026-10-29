"""Проверки обновления публичной карты после изменения маршрута"""

from unittest.mock import AsyncMock, call

import pytest

from app.schemas.admin_stage_route import StageRouteReplaceRequest
from tests.test_services.test_admin_stage_route import _service


@pytest.mark.parametrize("clear", [False, True])
async def test_route_cache_is_invalidated_after_commit(monkeypatch, clear):
    """Успешная замена или очистка сбрасывает кэш маршрута после коммита"""
    service, session = _service()
    invalidate_patterns = AsyncMock()
    monkeypatch.setattr(
        "app.services.admin_stage_route.cache.invalidate_pattern", invalidate_patterns
    )

    async def invalidate(_):
        session.commit.assert_awaited_once()

    invalidate_patterns.side_effect = invalidate
    if clear:
        service.routes.list_for_stage.return_value = [type("Point", (), {"lat": 53, "lon": 158})()]
        await service.clear_route(1, admin_id=7)
    else:
        body = StageRouteReplaceRequest(points=[{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}])
        await service.replace_route(1, body, admin_id=7)

    assert invalidate_patterns.await_args_list == [
        call("public:map:*"),
        call("public:stages:*"),
        call("admin:*"),
    ]


async def test_failed_commit_does_not_invalidate_route_cache(monkeypatch):
    """Если запись не сохранилась, кэш маршрута не объявляется обновлённым"""
    service, session = _service()
    session.commit.side_effect = RuntimeError("Ошибка хранилища")
    invalidate_patterns = AsyncMock()
    monkeypatch.setattr(
        "app.services.admin_stage_route.cache.invalidate_pattern", invalidate_patterns
    )
    body = StageRouteReplaceRequest(points=[{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}])

    with pytest.raises(RuntimeError):
        await service.replace_route(1, body, admin_id=7)
    invalidate_patterns.assert_not_awaited()
