"""Проверки динамических JSON-маршрутов встроенной админки"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.parametrize(
    "path", ["/admin-panel/api/race-route/7", "/admin-panel/api/participant-card/8"]
)
async def test_admin_detail_routes_require_authentication(client, path):
    """Маршрут существует и перенаправляет гостя на форму авторизации"""
    response = await client.get(path)
    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin-panel/login")


async def test_admin_route_passes_path_id_to_service(client, monkeypatch):
    """Число из URL карты передаётся сервису как ID этапа и возвращает JSON"""
    monkeypatch.setattr(
        "app.admin_panel.admin_auth.AdminPanelAuth.authenticate", AsyncMock(return_value=True)
    )

    @asynccontextmanager
    async def session():
        yield MagicMock()

    service = SimpleNamespace(
        get_route_by_stage=AsyncMock(return_value=[{"lat": 55, "lon": 160}]),
        get_checkpoints_by_stage=AsyncMock(return_value=[]),
    )
    monkeypatch.setattr("app.admin_panel.views.race_route.async_session_factory", session)
    monkeypatch.setattr("app.admin_panel.views.race_route.AdminRouteService", lambda _: service)

    response = await client.get("/admin-panel/api/race-route/7")

    assert response.status_code == 200
    assert response.json() == {"route": [{"lat": 55, "lon": 160}], "checkpoints": []}
    service.get_route_by_stage.assert_awaited_once_with(7)
    service.get_checkpoints_by_stage.assert_awaited_once_with(7)


async def test_admin_participant_route_handles_missing_card(client, monkeypatch):
    """ID карточки извлекается из URL, а отсутствие участника даёт 404"""
    monkeypatch.setattr(
        "app.admin_panel.admin_auth.AdminPanelAuth.authenticate", AsyncMock(return_value=True)
    )

    @asynccontextmanager
    async def session():
        yield MagicMock()

    service = SimpleNamespace(get_participant_detail=AsyncMock(return_value=None))
    monkeypatch.setattr("app.admin_panel.views.participant_card.async_session_factory", session)
    monkeypatch.setattr(
        "app.admin_panel.views.participant_card.AdminParticipantService", lambda _: service
    )

    response = await client.get("/admin-panel/api/participant-card/8")

    assert response.status_code == 404
    assert response.json() == {"error": "not found"}
    service.get_participant_detail.assert_awaited_once_with(8)


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ({}, "ok"),
        ({"is_active": False}, "inactive"),
        ({"sos_active": True}, "sos"),
        ({"battery_percent": 10}, "low_battery"),
    ],
)
async def test_participant_card_uses_real_device_health(
    client, db_session, create_participant, create_device, monkeypatch, attributes, expected
):
    """Страница и JSON карточки работают с моделью Device без выдуманного поля status"""
    participant = await create_participant()
    device = await create_device(participant_id=participant.id)
    for name, value in attributes.items():
        setattr(device, name, value)
    await db_session.flush()
    monkeypatch.setattr(
        "app.admin_panel.admin_auth.AdminPanelAuth.authenticate", AsyncMock(return_value=True)
    )

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr("app.admin_panel.views.participant_card.async_session_factory", session)

    page = await client.get("/admin-panel/participants-card")
    response = await client.get(f"/admin-panel/api/participant-card/{participant.id}")

    assert page.status_code == 200
    assert response.status_code == 200
    assert response.json()["device_status"] == expected
