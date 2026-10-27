"""Проверки загрузки маршрута через настоящие маршруты SQLAdmin"""

import re
from contextlib import asynccontextmanager
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend

from app.admin_panel.views.race_route import RaceRouteView

GPX = b'<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><rte><rtept lat="53" lon="158"/><rtept lat="54" lon="159"/></rte></gpx>'


async def test_import_and_map_share_full_width_column(route_client):
    """Общая сетка админки получает одну колонку с формой и картой, а не вложенную строку"""

    class LayoutParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parents = []
            self.found = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if attributes.get("id") in {"stageRoutePage", "routeImport", "routeMap"}:
                self.found[attributes["id"]] = list(self.parents)
            if tag not in {
                "area",
                "base",
                "br",
                "col",
                "embed",
                "hr",
                "img",
                "input",
                "link",
                "meta",
                "param",
                "source",
                "track",
                "wbr",
            }:
                self.parents.append((tag, attributes))

        def handle_endtag(self, tag):
            for i in range(len(self.parents) - 1, -1, -1):
                if self.parents[i][0] == tag:
                    del self.parents[i:]
                    break

    client, _ = route_client
    response = await client.get("/admin/race-route", headers={"X-Test-Admin": "yes"})
    assert response.status_code == 200
    parser = LayoutParser()
    parser.feed(response.text)
    assert "stageRoutePage" in parser.found
    assert "row-deck" in parser.found["stageRoutePage"][-1][1].get("class", "").split()
    for target in ("routeImport", "routeMap"):
        assert any(attrs.get("id") == "stageRoutePage" for _, attrs in parser.found[target])
        column = next(
            attrs for _, attrs in parser.found[target] if attrs.get("id") == "stageRoutePage"
        )
        assert "d-block" in column.get("class", "").split()


@pytest.fixture
async def route_client(monkeypatch):
    """Подключает реальный экран к тестовой сессии без обращения к рабочей БД"""

    class Auth(AuthenticationBackend):
        async def authenticate(self, request):
            request.state.admin_id = 7
            return request.headers.get("X-Test-Admin") == "yes"

    class TestRouteView(RaceRouteView):
        """Не меняет служебные атрибуты экрана, зарегистрированного в общем приложении"""

    app = FastAPI()
    admin = Admin(
        app,
        templates_dir="app/templates",
        authentication_backend=Auth(secret_key="test-route-import"),
    )
    admin.add_view(TestRouteView)

    @asynccontextmanager
    async def session():
        yield MagicMock()

    service = SimpleNamespace(
        get_route=AsyncMock(return_value=[]),
        replace_route=AsyncMock(
            return_value=[
                SimpleNamespace(position=0, lat=53, lon=158),
                SimpleNamespace(position=1, lat=54, lon=159),
            ]
        ),
    )
    directory = SimpleNamespace(get_stages=AsyncMock(return_value=[]))
    monkeypatch.setattr("app.admin_panel.views.race_route.async_session_factory", session)
    monkeypatch.setattr("app.admin_panel.views.race_route.AdminRouteService", lambda _: directory)
    monkeypatch.setattr(
        "app.admin_panel.views.race_route.AdminStageRouteService", lambda _: service, raising=False
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, service


async def _token(client):
    """Получает токен подтверждения из страницы авторизованного администратора"""
    response = await client.get("/admin/race-route", headers={"X-Test-Admin": "yes"})
    assert response.status_code == 200
    return re.search(r'data-csrf="([^"]+)"', response.text).group(1)


async def test_preview_returns_coordinates_without_saving(route_client):
    """Предпросмотр разбирает файл для выбранного этапа, но не меняет маршрут"""
    client, service = route_client
    token = await _token(client)
    response = await client.post(
        "/admin/api/race-route/1/import/preview",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        files={"file": ("route.gpx", GPX, "application/gpx+xml")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "stage_id": 1,
        "points": [{"lat": 53.0, "lon": 158.0}, {"lat": 54.0, "lon": 159.0}],
    }
    service.get_route.assert_awaited_once_with(1)
    service.replace_route.assert_not_awaited()


async def test_confirmation_saves_using_authenticated_admin(route_client):
    """Подтверждение передаёт координаты и ID администратора общему сервису маршрута"""
    client, service = route_client
    token = await _token(client)
    response = await client.post(
        "/admin/api/race-route/1/import/confirm",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        json={"points": [{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}]},
    )
    assert response.status_code == 200
    assert response.json()["stage_id"] == 1
    assert len(response.json()["points"]) == 2
    args, kwargs = service.replace_route.await_args
    assert args[0] == 1
    assert args[1].points[0].lat == 53
    assert kwargs == {"admin_id": 7}


@pytest.mark.parametrize("action", ["preview", "confirm"])
async def test_import_requires_admin_session(route_client, action):
    """Неавторизованный посетитель не может просматривать или сохранять импорт"""
    client, service = route_client
    response = await client.post(f"/admin/api/race-route/1/import/{action}")
    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin/login")
    service.get_route.assert_not_awaited()
    service.replace_route.assert_not_awaited()


@pytest.mark.parametrize("action", ["preview", "confirm"])
async def test_import_rejects_missing_or_wrong_csrf_token(route_client, action):
    """Даже активной сессии недостаточно без токена этой формы"""
    client, service = route_client
    await _token(client)
    response = await client.post(
        f"/admin/api/race-route/1/import/{action}",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": "wrong"},
        json={"points": [{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}]},
    )
    assert response.status_code == 403
    service.replace_route.assert_not_awaited()


@pytest.mark.parametrize("body", [{"points": []}, {"points": [{"lat": 91, "lon": 0}]}])
async def test_confirmation_rejects_invalid_coordinates(route_client, body):
    """Невалидное подтверждение не очищает и не изменяет сохранённый маршрут"""
    client, service = route_client
    token = await _token(client)
    response = await client.post(
        "/admin/api/race-route/1/import/confirm",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        json=body,
    )
    assert response.status_code == 422
    service.replace_route.assert_not_awaited()


async def test_preview_rejects_oversized_upload(route_client):
    """Файл больше 2 МиБ отклоняется до попытки сохранения маршрута"""
    client, service = route_client
    token = await _token(client)
    response = await client.post(
        "/admin/api/race-route/1/import/preview",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        files={"file": ("route.gpx", b"x" * (2 * 1024 * 1024 + 1))},
    )
    assert response.status_code == 413
    service.replace_route.assert_not_awaited()


async def test_confirmation_preserves_route_conflict_response(route_client):
    """Изменение этапа с GPS-точками возвращает 409 из существующего сервиса"""
    from fastapi import HTTPException

    client, service = route_client
    token = await _token(client)
    service.replace_route.side_effect = HTTPException(409, "Маршрут менять нельзя")
    response = await client.post(
        "/admin/api/race-route/1/import/confirm",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        json={"points": [{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}]},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Маршрут менять нельзя"


@pytest.mark.parametrize(
    "upload", [None, ("route.csv", b"53,158\n54,159"), ("route.gpx", b"<broken")]
)
async def test_preview_rejects_missing_or_invalid_file(route_client, upload):
    """Отсутствующий файл, чужое расширение и повреждённый XML дают 422 без записи"""
    client, service = route_client
    token = await _token(client)
    kwargs = {"files": {"file": upload}} if upload else {}
    response = await client.post(
        "/admin/api/race-route/1/import/preview",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        **kwargs,
    )
    assert response.status_code == 422
    service.replace_route.assert_not_awaited()


async def test_chunked_request_is_limited_without_content_length(route_client):
    """Потоковая загрузка без Content-Length тоже ограничена по общему размеру"""
    client, service = route_client
    token = await _token(client)

    async def stream():
        for _ in range(40):
            yield b"x" * 65536

    response = await client.post(
        "/admin/api/race-route/1/import/preview",
        headers={
            "X-Test-Admin": "yes",
            "X-Route-Import-Token": token,
            "Content-Type": "multipart/form-data; boundary=route",
        },
        content=stream(),
    )
    assert response.status_code == 413
    service.replace_route.assert_not_awaited()


async def test_preview_preserves_missing_stage_response(route_client):
    """Файл для удалённого этапа возвращает 404 и не создаёт маршрут"""
    from fastapi import HTTPException

    client, service = route_client
    token = await _token(client)
    service.get_route.side_effect = HTTPException(404, "Этап не найден")
    response = await client.post(
        "/admin/api/race-route/1/import/preview",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        files={"file": ("route.gpx", GPX)},
    )
    assert response.status_code == 404
    service.replace_route.assert_not_awaited()


@pytest.mark.parametrize("stage_id", [0, 2147483648])
async def test_import_rejects_stage_id_outside_database_range(route_client, stage_id):
    """Некорректный ID этапа отклоняется до обращения к хранилищу"""
    client, service = route_client
    token = await _token(client)
    response = await client.post(
        f"/admin/api/race-route/{stage_id}/import/preview",
        headers={"X-Test-Admin": "yes", "X-Route-Import-Token": token},
        files={"file": ("route.gpx", GPX)},
    )
    assert response.status_code == 422
    service.get_route.assert_not_awaited()
