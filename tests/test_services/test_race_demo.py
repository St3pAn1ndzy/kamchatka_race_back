"""Проверки демонстрационного движения и восстановления трекера"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.models.track_point import TrackPoint
from app.services.admin_dashboard import AdminDashboardService
from app.services.cache import cache
from app.services.public_map import PublicMapService
from app.services.race_demo import RaceDemo, check_demo_settings


def test_production_is_rejected():
    """Демонстрация не запускается с рабочими или удалёнными настройками"""
    from app.config import Settings

    with pytest.raises(ValueError):
        check_demo_settings(Settings(ENV="prod"))
    with pytest.raises(ValueError):
        check_demo_settings(Settings(ENV="dev", POSTGRES_HOST="example.org"))


async def test_demo_moves_and_restores(
    db_session,
    create_season,
    create_stage,
    create_participant,
    create_device,
    create_route_point,
    create_discipline,
):
    """Две демоточки меняют координаты и SOS, очистка сохраняет прежнюю точку"""
    db_session.sync_session.expire_on_commit = False
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    discipline = await create_discipline(season_id=season.id)
    participant = await create_participant(discipline_id=discipline.id)
    device = await create_device(participant_id=participant.id, stage_id=stage.id)
    old_time = datetime(2026, 1, 1, tzinfo=UTC)
    device.last_message_at = old_time
    device.sos_active = True
    await create_route_point(stage_id=stage.id, position=0, lat=53, lon=158)
    await create_route_point(stage_id=stage.id, position=1, lat=53.01, lon=158.01)
    old = TrackPoint(
        device_id=device.id,
        participant_id=participant.id,
        stage_id=stage.id,
        lat=52,
        lon=157,
        recorded_at=old_time,
        deduplication_key="old-demo-test",
    )
    db_session.add(old)
    await db_session.flush()
    old_id = old.id
    demo = await RaceDemo.prepare(db_session, device.id)
    first = await demo.tick(0, sos=False)
    await db_session.commit()
    assert await AdminDashboardService(db_session).get_sos_devices() == []
    first_positions = await PublicMapService(db_session).get_positions(stage.id)
    assert first_positions[0].lat == first.lat
    second = await demo.tick(1, sos=True)
    await db_session.commit()
    await demo.invalidate_cache()
    assert (first.lat, first.lon) != (second.lat, second.lon)
    assert second.is_confirmed
    assert device.sos_active is True
    assert device.last_message_at > old_time
    alarms = await AdminDashboardService(db_session).get_sos_devices()
    assert len(alarms) == 1
    assert alarms[0].device_id == device.id
    assert (alarms[0].lat, alarms[0].lon) == (second.lat, second.lon)
    positions = await PublicMapService(db_session).get_positions(stage.id)
    assert len(positions) == 1
    assert (positions[0].lat, positions[0].lon) == (second.lat, second.lon)
    assert "sos" not in positions[0].model_dump()
    key = f"public:map:model:{stage.id}:100:0"
    await cache.set(key, {"old": True}, ttl=60)
    await cache.set("admin:dashboard:stats", {"old": True}, ttl=60)
    await demo.invalidate_cache()
    assert await cache.get(key) is None
    assert await cache.get("admin:dashboard:stats") is None
    await demo.cleanup()
    await db_session.commit()
    assert device.sos_active is True
    assert device.last_message_at == old_time
    assert list((await db_session.scalars(select(TrackPoint.id))).all()) == [old_id]


async def test_demo_rejects_device_without_route(
    db_session,
    create_season,
    create_stage,
    create_participant,
    create_device,
):
    """Без линии этапа скрипт не выдумывает координаты и не меняет SOS"""
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    participant = await create_participant()
    device = await create_device(participant_id=participant.id, stage_id=stage.id)
    with pytest.raises(ValueError, match="маршрут"):
        await RaceDemo.prepare(db_session, device.id)
    assert not device.sos_active


@pytest.mark.parametrize("database,redis_db", [("avacha", 13), ("avacha_demo_overview", 0)])
def test_direct_demo_rejects_shared_resources(database, redis_db):
    """Прямой запуск не пишет демоточки в основную базу или общий кеш"""
    from app.config import Settings

    with pytest.raises(ValueError):
        check_demo_settings(
            Settings(
                ENV="dev",
                POSTGRES_HOST="localhost",
                REDIS_HOST="localhost",
                POSTGRES_DB=database,
                REDIS_DB=redis_db,
            )
        )


@pytest.fixture
async def prepared_demo(
    db_session, create_season, create_stage, create_participant, create_device, create_route_point
):
    """Создаёт привязанный трекер с линией для проверки остановки демонстрации"""
    db_session.sync_session.expire_on_commit = False
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    participant = await create_participant()
    device = await create_device(participant_id=participant.id, stage_id=stage.id)
    await create_route_point(stage_id=stage.id, position=0, lat=53, lon=158)
    await create_route_point(stage_id=stage.id, position=1, lat=53.01, lon=158.01)
    demo = await RaceDemo.prepare(db_session, device.id)
    return demo


async def test_cleanup_after_rollback_uses_saved_device_id(db_session, prepared_demo):
    """После rollback очистка удаляет ранее зафиксированные точки без неявной загрузки ORM"""
    demo = prepared_demo
    await demo.tick(0, sos=True)
    await db_session.commit()
    await db_session.execute(select(TrackPoint.id))
    await db_session.rollback()
    await demo.cleanup()
    await db_session.commit()
    assert list(await db_session.scalars(select(TrackPoint.id))) == []


async def test_cleanup_preserves_newer_device_message(db_session, prepared_demo):
    """Очистка не затирает более поздний SOS и время сообщения другого источника"""
    from datetime import timedelta

    demo = prepared_demo
    point = await demo.tick(0, sos=False)
    await db_session.commit()
    newer = point.recorded_at + timedelta(seconds=10)
    demo.device.sos_active = True
    demo.device.last_message_at = newer
    await db_session.commit()
    await demo.cleanup()
    await db_session.commit()
    assert demo.device.sos_active is True
    assert demo.device.last_message_at == newer
    assert list(await db_session.scalars(select(TrackPoint.id))) == []


async def test_second_demo_rejected_while_first_has_points(db_session, prepared_demo):
    """Второй запуск не перехватывает устройство с незавершённой демонстрацией"""
    demo = prepared_demo
    await demo.tick(0, sos=True)
    await db_session.commit()
    with pytest.raises(ValueError, match="демонстрац"):
        await RaceDemo.prepare(db_session, demo.device.id)
    await demo.cleanup()
