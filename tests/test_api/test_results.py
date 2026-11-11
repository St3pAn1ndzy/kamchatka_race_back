from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_result_service
from app.api.v1 import results as results_router
from app.api.v1.results import control_times, leaderboard, stage_protocol, standings
from app.enums import PublicationStatus
from app.schemas.results import RaceStandings, StageProtocol


async def test_standings_returns_service_result():
    """Сводная таблица возвращает результат сервиса без преобразований"""
    service = AsyncMock()
    expected = RaceStandings(rows=[])
    service.get_standings.return_value = expected
    assert await standings(service) is expected
    service.get_standings.assert_awaited_once_with(discipline_id=None, season_id=None)


async def test_draft_stage_is_not_exposed():
    """Неопубликованный протокол недоступен и возвращает 404"""
    service = AsyncMock()
    service.get_stage_protocol.return_value = None
    with pytest.raises(HTTPException) as exc:
        await stage_protocol(8, service)
    assert exc.value.status_code == 404
    service.get_stage_protocol.assert_awaited_once_with(8, discipline_id=None)


async def test_published_stage_is_returned():
    """Опубликованный протокол этапа возвращается клиенту"""
    service = AsyncMock()
    expected = StageProtocol(
        stage_id=8, stage_name="Stage", publication=PublicationStatus.OFFICIAL, rows=[]
    )
    service.get_stage_protocol.return_value = expected
    assert await stage_protocol(8, service) is expected


async def test_leaderboard_passes_limit():
    """Ограничение размера таблицы лидеров передаётся сервису"""
    service = AsyncMock()
    service.get_leaderboard.return_value = []
    assert await leaderboard(service, limit=17) == []
    service.get_leaderboard.assert_awaited_once_with(limit=17, discipline_id=None, season_id=None)


async def test_control_times_passes_stage_filter():
    """Фильтр этапа передаётся при запросе отметок участника"""
    service = AsyncMock()
    service.get_control_times.return_value = []
    assert await control_times(12, service, stage_id=3) == []
    service.get_control_times.assert_awaited_once_with(12, stage_id=3)


@pytest.mark.parametrize("path", ["/results/stage/0", "/results/leaderboard?limit=201"])
async def test_http_rejects_invalid_result_parameters(path):
    """HTTP-запросы с неверным ID этапа или limit получают 422"""
    app = FastAPI()
    app.include_router(results_router.router)
    service = AsyncMock()
    app.dependency_overrides[get_result_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 422
    service.get_stage_protocol.assert_not_awaited()
    service.get_leaderboard.assert_not_awaited()


async def test_stage_protocol_404_for_unknown_stage(client) -> None:
    """404 только если этапа нет в БД."""
    response = await client.get("/api/v1/results/stage/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_stage_protocol_draft_returns_200(client, create_season, create_stage) -> None:
    """DRAFT-этап → 200 с publication=draft и пустыми rows."""
    season = await create_season(is_active=True)
    stage = await create_stage(season_id=season.id)

    response = await client.get(f"/api/v1/results/stage/{stage.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["publication"] == "draft"
    assert data["rows"] == []
    assert data["stage_id"] == stage.id
