"""Проверки общего импорта через авторизацию и CSRF SQLAdmin"""

# ruff: noqa: F811

import json

from sqlalchemy import func, select

from app.db.models.checkpoint import Checkpoint
from app.db.models.stage_route_point import StageRoutePoint
from tests.test_api.test_route_import_integration import _token, import_client  # noqa: F401, F811

KML = b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Folder><name>Stage 1</name>
<Placemark><name>Start</name><Point><coordinates>158,53,100</coordinates></Point></Placemark>
<Placemark><name>Finish</name><Point><coordinates>158.01,53.01,200</coordinates></Point></Placemark>
<Placemark><name>Track</name><LineString><coordinates>158,53,100 158.01,53.01,200</coordinates></LineString></Placemark>
</Folder></Document></kml>"""


async def test_whole_race_import_authentication(client):
    """Гость не может открыть ни предпросмотр, ни подтверждение общего импорта"""
    for action in ("preview", "confirm"):
        response = await client.post(
            f"/admin-panel/api/race-route/import/{action}", files={"file": ("race.kml", KML)}
        )
        assert response.status_code == 302


async def test_full_import_preview_confirm_and_csrf(
    import_client,
    db_session,
    create_season,
    create_stage,
):
    """Предпросмотр не пишет в БД, подтверждение сохраняет КП и высоты с действующим CSRF"""
    client, _ = import_client
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    token = await _token(client)
    path = "/admin-panel/api/race-route/import/"
    forbidden = await client.post(path + "preview", files={"file": ("race.kml", KML)})
    assert forbidden.status_code == 403
    headers = {"X-Route-Import-Token": token}
    preview = await client.post(
        path + "preview", headers=headers, files={"file": ("race.kml", KML)}
    )
    assert preview.status_code == 200
    assert preview.json()["lines"][0]["point_count"] == 2
    assert await db_session.scalar(select(func.count(StageRoutePoint.id))) == 0
    mapping = [
        {
            "stage_id": stage.id,
            "reverse": False,
            "direction_confirmed": True,
            "kinds": ["start", "finish"],
        }
    ]
    confirm = await client.post(
        path + "confirm",
        headers=headers,
        files={"file": ("race.kml", KML)},
        data={"mapping": json.dumps(mapping)},
    )
    assert confirm.status_code == 200, confirm.text
    assert await db_session.scalar(select(func.count(Checkpoint.id))) == 2
    points = list(
        await db_session.scalars(select(StageRoutePoint).order_by(StageRoutePoint.position))
    )
    assert [p.elevation for p in points] == [100, 200]
