"""Проверки импорта с настоящими PostgreSQL, Redis и сессией администратора"""

import re
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.db.models.audit_log import AuditLog
from app.db.models.stage_route_point import StageRoutePoint
from app.services.cache import cache

GPX = b'<gpx xmlns="http://www.topografix.com/GPX/1/1"><rte><rtept lat="53" lon="158"/><rtept lat="54" lon="159"/></rte></gpx>'
KML = b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString><coordinates>158,53,100 159,54,200</coordinates></LineString></Placemark></kml>'


@pytest.fixture
async def import_client(client, app, db_session, monkeypatch, create_admin):
    """Подключает панель к тестовой транзакции с настройкой сессии как в приложении"""
    monkeypatch.setattr(db_session.sync_session, "expire_on_commit", False)
    await cache.close()

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr("app.admin_panel.admin_auth.async_session_factory", session)
    monkeypatch.setattr("app.admin_panel.views.race_route.async_session_factory", session)
    admin = await create_admin()
    login = await client.post(
        "/admin-panel/login", data={"username": "admin", "password": "admin123"}
    )
    assert login.status_code == 302
    try:
        yield client, admin.id
    finally:
        # Каждый тест получает свой event loop, поэтому соединения не переносим между тестами
        await app.state.admin_login_limiter.close()
        await cache.close()


async def _token(client):
    """Получает настоящий CSRF-токен страницы после входа через форму панели"""
    response = await client.get("/admin-panel/race-route")
    assert response.status_code == 200
    return re.search(r'data-csrf="([^"]+)"', response.text).group(1)


async def _points(session, stage_id):
    """Читает сохранённый порядок координат непосредственно из тестовой базы"""
    points = (
        await session.scalars(
            select(StageRoutePoint)
            .where(StageRoutePoint.stage_id == stage_id)
            .order_by(StageRoutePoint.position)
        )
    ).all()
    return [(p.position, p.lat, p.lon) for p in points]


@pytest.mark.parametrize(("filename", "content"), [("route.gpx", GPX), ("route.kml", KML)])
async def test_import_saves_route_audit_and_refreshes_public_map(
    import_client, db_session, create_season, create_stage, create_route_point, filename, content
):
    """Предпросмотр не пишет в БД, подтверждение сохраняет порядок, аудит и обновляет карту"""
    client, admin_id = import_client
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    stage_id = stage.id
    await create_route_point(stage_id=stage_id, position=0, lat=50, lon=150)
    await create_route_point(stage_id=stage_id, position=1, lat=51, lon=151)
    public_path = f"/api/v1/stages/{stage_id}/track"
    previous = await client.get(public_path)
    assert previous.status_code == 200
    assert previous.json()["coordinates"] == [[150, 50], [151, 51]]
    assert await cache.get(f"public:map:route:{stage_id}") is not None

    token = await _token(client)
    headers = {"X-Route-Import-Token": token}
    preview = await client.post(
        f"/admin-panel/api/race-route/{stage_id}/import/preview",
        headers=headers,
        files={"file": (filename, content)},
    )
    assert preview.status_code == 200
    assert await _points(db_session, stage_id) == [(0, 50, 150), (1, 51, 151)]
    query = select(AuditLog).where(
        AuditLog.action == "stage_route_replaced", AuditLog.entity_id == str(stage_id)
    )
    assert (await db_session.scalars(query)).all() == []

    confirm = await client.post(
        f"/admin-panel/api/race-route/{stage_id}/import/confirm",
        headers=headers,
        json={"points": preview.json()["points"]},
    )
    assert confirm.status_code == 200
    assert await _points(db_session, stage_id) == [(0, 53, 158), (1, 54, 159)]
    audit = (await db_session.scalars(query)).one()
    assert audit.admin_id == admin_id
    assert audit.payload == {
        "old": [{"lat": 50, "lon": 150}, {"lat": 51, "lon": 151}],
        "new": [{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}],
    }
    assert await cache.get(f"public:map:route:{stage_id}") is None
    updated = await client.get(public_path)
    assert updated.status_code == 200
    assert updated.json()["coordinates"] == [[158, 53], [159, 54]]


async def test_import_replaces_stage_without_deleting_real_track_points(
    import_client,
    db_session,
    create_season,
    create_stage,
    create_route_point,
    create_discipline,
    create_participant,
    create_track_point,
):
    """Замена маршрута с GPS-историей сохраняет точку и записывает аудит"""
    client, _ = import_client
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    discipline = await create_discipline(season_id=season.id)
    participant = await create_participant(discipline_id=discipline.id)
    stage_id = stage.id
    await create_route_point(stage_id=stage_id, position=0, lat=50, lon=150)
    await create_route_point(stage_id=stage_id, position=1, lat=51, lon=151)
    point = await create_track_point(participant_id=participant.id, stage_id=stage_id)
    point_id, coordinates = point.id, (point.lat, point.lon)
    token = await _token(client)

    response = await client.post(
        f"/admin-panel/api/race-route/{stage_id}/import/confirm",
        headers={"X-Route-Import-Token": token},
        json={"points": [{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}]},
    )
    assert response.status_code == 200
    assert await _points(db_session, stage_id) == [(0, 53, 158), (1, 54, 159)]
    from app.db.models.track_point import TrackPoint

    saved = await db_session.get(TrackPoint, point_id)
    assert (saved.lat, saved.lon) == coordinates
    assert (
        len(
            (
                await db_session.scalars(
                    select(AuditLog).where(
                        AuditLog.action == "stage_route_replaced",
                        AuditLog.entity_id == str(stage_id),
                    )
                )
            ).all()
        )
        == 1
    )
