"""Регрессии погодной замены линии, километража и переносимого прогресса"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint
from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.admin_stage_route import AdminStageRouteService
from app.services.cache import cache
from app.services.tracking_metrics import (
    TrackingMetricsService,
    _distance_km,
    reproject_latest_points,
)


def route():
    """Создаёт линию вдоль экватора для проверяемого расчёта расстояния"""
    return [StageRoutePoint(lat=0, lon=0), StageRoutePoint(lat=0, lon=0.02)]


async def test_line_replacement_updates_distance_checkpoints_and_track_cache(
    db_session,
    create_admin,
    create_season,
    create_stage,
    create_checkpoint,
    create_route_point,
    create_participant,
    create_track_point,
    create_official_mark,
):
    """Смена линии синхронизирует длину, КП следующих этапов и публичный трек без потери отметок"""
    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id, distance_km=10, order_index=1)
    stage.status = "active"
    following = await create_stage(season_id=season.id, number=2, order_index=2)
    start = await create_checkpoint(
        stage_id=stage.id, kind="start", lat=0, lon=0, km_from_race_start=0
    )
    finish = await create_checkpoint(
        stage_id=stage.id, kind="finish", lat=0, lon=0.02, km_from_race_start=10
    )
    later_cp = await create_checkpoint(stage_id=following.id, km_from_race_start=15)
    await create_route_point(stage_id=stage.id, lat=0, lon=0)
    await create_route_point(stage_id=stage.id, position=1, lat=0, lon=0.01)
    participant = await create_participant()
    mark = await create_official_mark(participant_id=participant.id, checkpoint_id=start.id)
    gps = await create_track_point(
        participant_id=participant.id, stage_id=stage.id, lat=0, lon=0.01, km_from_start=0.4
    )
    key = f"public:map:track:{stage.id}:{participant.id}:100:0"
    await cache.set(key, {"old": True}, ttl=60)
    await AdminStageRouteService(db_session).replace_route(
        stage.id,
        StageRouteReplaceRequest(points=[{"lat": 0, "lon": 0}, {"lat": 0, "lon": 0.02}]),
        admin_id=admin.id,
    )
    await db_session.refresh(later_cp)
    assert stage.distance_km == pytest.approx(_distance_km(0, 0, 0, 0.02))
    assert finish.km_from_race_start == pytest.approx(stage.distance_km)
    assert later_cp.km_from_race_start == pytest.approx(stage.distance_km + 5)
    assert gps.km_from_start == pytest.approx(stage.distance_km / 2)
    assert (gps.lat, gps.lon) == (0, 0.01)
    assert mark.checkpoint_id == start.id
    assert await cache.get(key) is None


async def test_reprojection_carries_latest_valid_fix_and_preserves_older_rows(
    db_session,
    create_season,
    create_stage,
    create_participant,
    create_track_point,
):
    """Последние точки вне новой трассы получают прогресс предыдущей пригодной координаты"""
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    participant = await create_participant()
    now = datetime.now(UTC)
    older = await create_track_point(
        participant_id=participant.id,
        stage_id=stage.id,
        lat=0,
        lon=0.005,
        recorded_at=now,
        km_from_start=55,
    )
    latest = await create_track_point(
        participant_id=participant.id,
        stage_id=stage.id,
        device_id=older.device_id,
        lat=0.02,
        lon=0.005,
        recorded_at=now + timedelta(minutes=1),
        km_from_start=55,
    )
    await reproject_latest_points(db_session, stage.id, route())
    assert latest.km_from_start == pytest.approx(0.5559754)
    assert older.km_from_start == 55
    following = TrackPoint(
        device_id=older.device_id,
        participant_id=participant.id,
        stage_id=stage.id,
        lat=0.021,
        lon=0.005,
        recorded_at=now + timedelta(minutes=2),
    )
    await TrackingMetricsService(db_session).fill_metrics(following)
    assert following.km_from_start == latest.km_from_start


async def test_reprojection_does_not_borrow_another_devices_progress(
    db_session,
    create_season,
    create_stage,
    create_participant,
    create_track_point,
):
    """Устройство без подходящей истории не заимствует километраж другого назначения"""
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    first = await create_participant(number=1)
    second = await create_participant(number=2)
    valid = await create_track_point(participant_id=first.id, stage_id=stage.id, lat=0, lon=0.01)
    invalid = await create_track_point(
        participant_id=second.id, stage_id=stage.id, lat=0.03, lon=0.01
    )
    await reproject_latest_points(db_session, stage.id, route())
    assert valid.km_from_start is not None
    assert invalid.km_from_start is None


async def test_line_only_rejects_moved_checkpoint_before_writing(
    db_session,
    create_admin,
    create_season,
    create_stage,
    create_checkpoint,
    create_route_point,
):
    """Отдельная линия не оставляет КП вне трассы и предлагает совместный импорт"""
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    await create_checkpoint(stage_id=stage.id, lat=10, lon=10)
    point = await create_route_point(stage_id=stage.id, lat=10, lon=10)
    with pytest.raises(HTTPException) as error:
        await AdminStageRouteService(db_session).replace_route(
            stage.id,
            StageRouteReplaceRequest(points=[{"lat": 0, "lon": 0}, {"lat": 0, "lon": 0.02}]),
            admin_id=admin.id,
        )
    assert error.value.status_code == 409
    assert "маршрута с КП" in error.value.detail
    assert list(await db_session.scalars(select(StageRoutePoint))) == [point]


async def test_line_replacement_reorders_existing_checkpoints_by_new_geometry(
    db_session,
    create_admin,
    create_season,
    create_stage,
    create_checkpoint,
):
    """Изменённая линия задаёт новый порядок КП без смены их идентификаторов"""
    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    start = await create_checkpoint(stage_id=stage.id, kind="start", lat=0, lon=0, order_index=0)
    a = await create_checkpoint(stage_id=stage.id, lat=0, lon=0.03, order_index=1)
    b = await create_checkpoint(stage_id=stage.id, lat=0.03, lon=0.03, order_index=2)
    finish = await create_checkpoint(
        stage_id=stage.id, kind="finish", lat=0.03, lon=0, order_index=3
    )
    await AdminStageRouteService(db_session).replace_route(
        stage.id,
        StageRouteReplaceRequest(
            points=[{"lat": cp.lat, "lon": cp.lon} for cp in (start, b, a, finish)]
        ),
        admin_id=admin.id,
    )
    assert b.km_from_race_start < a.km_from_race_start
    assert [cp.order_index for cp in (start, b, a, finish)] == [0, 1, 2, 3]
