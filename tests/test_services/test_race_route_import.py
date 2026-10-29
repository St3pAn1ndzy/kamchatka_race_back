"""Проверки атомарного импорта этапов и контрольных пунктов"""

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.models.audit_log import AuditLog
from app.db.models.checkpoint import Checkpoint
from app.db.models.stage_route_point import StageRoutePoint
from app.services.cache import cache
from app.services.race_route_import import RaceRouteImportService


def line():
    """Возвращает небольшой маршрут с высотой и точками старта и финиша"""
    return {
        "name": "Этап",
        "points": [
            {"lat": 53.0, "lon": 158.0, "elevation": 100.5},
            {"lat": 53.01, "lon": 158.01, "elevation": 120.5},
        ],
        "checkpoints": [
            {"name": "Старт", "lat": 53.0, "lon": 158.0, "elevation": 100.5},
            {"name": "Финиш", "lat": 53.01, "lon": 158.01, "elevation": 120.5},
        ],
        "warnings": [],
    }


async def test_import_saves_and_replaces_without_duplicates(
    db_session,
    create_admin,
    create_season,
    create_stage,
):
    """Повторный импорт заменяет точки и КП без дубликатов и сохраняет высоты"""
    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    mapping = [
        {
            "stage_id": stage.id,
            "reverse": True,
            "direction_confirmed": True,
            "kinds": ["finish", "start"],
        }
    ]
    service = RaceRouteImportService(db_session)
    for _ in range(2):
        await service.save([line()], mapping, admin_id=admin.id, file_hash="example")
    points = list(
        await db_session.scalars(select(StageRoutePoint).order_by(StageRoutePoint.position))
    )
    cps = list(await db_session.scalars(select(Checkpoint).order_by(Checkpoint.order_index)))
    assert len(points) == len(cps) == 2
    assert points[0].lat == 53.01
    assert points[0].elevation == 120.5
    assert stage.distance_km > 0
    assert (
        len(
            list(
                await db_session.scalars(
                    select(AuditLog).where(AuditLog.action == "race_route_imported")
                )
            )
        )
        == 2
    )


@pytest.mark.parametrize("blocker", ["gps", "mark", "cancelled_mark"])
async def test_existing_race_data_is_never_deleted(
    db_session,
    create_admin,
    create_season,
    create_stage,
    create_participant,
    create_checkpoint,
    create_track_point,
    create_official_mark,
    blocker,
):
    """GPS и любые судейские отметки запрещают замену без удаления прежних КП"""
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    participant = await create_participant()
    cp = await create_checkpoint(stage_id=stage.id)
    if blocker == "gps":
        await create_track_point(participant_id=participant.id, stage_id=stage.id)
    else:
        await create_official_mark(
            participant_id=participant.id,
            checkpoint_id=cp.id,
            is_cancelled=blocker == "cancelled_mark",
        )
    with pytest.raises(HTTPException) as error:
        await RaceRouteImportService(db_session).save(
            [line()],
            [
                {
                    "stage_id": stage.id,
                    "reverse": False,
                    "direction_confirmed": True,
                    "kinds": ["start", "finish"],
                }
            ],
            admin_id=admin.id,
            file_hash="x",
        )
    assert error.value.status_code == 409
    assert await db_session.get(Checkpoint, cp.id) is cp


async def test_success_invalidates_only_after_commit(
    db_session,
    create_admin,
    create_season,
    create_stage,
):
    """После успешного импорта публичный маршрут и КП больше не читаются из старого кэша"""
    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    keys = [f"public:map:route:{stage.id}", f"public:map:checkpoint:{stage.id}"]
    for key in keys:
        await cache.set(key, {"old": True}, ttl=60)
    await RaceRouteImportService(db_session).save(
        [line()],
        [
            {
                "stage_id": stage.id,
                "reverse": False,
                "direction_confirmed": True,
                "kinds": ["start", "finish"],
            }
        ],
        admin_id=admin.id,
        file_hash="x",
    )
    for key in keys:
        assert await cache.get(key) is None


async def test_checkpoint_altitude_overflow_is_rejected_before_write(
    db_session,
    create_admin,
    create_season,
    create_stage,
):
    """Высота КП за пределами INTEGER даёт 422 без частичной замены маршрута"""
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    data = line()
    data["checkpoints"][0]["elevation"] = 2147483648.0
    with pytest.raises(HTTPException) as error:
        await RaceRouteImportService(db_session).save(
            [data],
            [
                {
                    "stage_id": stage.id,
                    "reverse": False,
                    "direction_confirmed": True,
                    "kinds": ["start", "finish"],
                }
            ],
            admin_id=admin.id,
            file_hash="x",
        )
    assert error.value.status_code == 422
    assert list(await db_session.scalars(select(StageRoutePoint))) == []


async def test_checkpoint_distance_follows_stage_order_index(
    db_session,
    create_admin,
    create_season,
    create_stage,
):
    """Километраж от старта гонки учитывает order_index даже при другом номере этапа"""
    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    later = await create_stage(season_id=season.id, number=1, order_index=20)
    earlier = await create_stage(season_id=season.id, number=2, order_index=10)
    mapping = [
        {
            "stage_id": s.id,
            "reverse": False,
            "direction_confirmed": True,
            "kinds": ["start", "finish"],
        }
        for s in (later, earlier)
    ]
    await RaceRouteImportService(db_session).save(
        [line(), line()], mapping, admin_id=admin.id, file_hash="x"
    )
    first_cp = await db_session.scalar(
        select(Checkpoint).where(Checkpoint.stage_id == earlier.id, Checkpoint.kind == "start")
    )
    assert first_cp.km_from_race_start == 0


async def test_any_started_stage_blocks_whole_package(
    db_session,
    create_admin,
    create_season,
    create_stage,
):
    """Запущенный второй этап не позволяет частично сохранить первый"""
    admin = await create_admin()
    season = await create_season()
    first = await create_stage(season_id=season.id)
    second = await create_stage(season_id=season.id, number=2)
    second.status = "active"
    await db_session.flush()
    mapping = [
        {
            "stage_id": s.id,
            "reverse": False,
            "direction_confirmed": True,
            "kinds": ["start", "finish"],
        }
        for s in (first, second)
    ]
    with pytest.raises(HTTPException) as error:
        await RaceRouteImportService(db_session).save(
            [line(), line()], mapping, admin_id=admin.id, file_hash="x"
        )
    assert error.value.status_code == 409
    assert list(await db_session.scalars(select(StageRoutePoint))) == []


async def test_active_stage_moves_existing_checkpoints_without_losing_marks(
    db_session,
    create_admin,
    create_season,
    create_stage,
    create_participant,
    create_checkpoint,
    create_track_point,
    create_official_mark,
):
    """Перенос КП на идущем этапе сохраняет их ID, отметки и исходные GPS-координаты"""
    from app.db.models.official_mark import OfficialMark

    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    stage.status = "active"
    participant = await create_participant()
    start = await create_checkpoint(stage_id=stage.id, name="Старт", kind="start")
    finish = await create_checkpoint(stage_id=stage.id, name="Финиш", kind="finish")
    mark = await create_official_mark(participant_id=participant.id, checkpoint_id=start.id)
    gps = await create_track_point(
        participant_id=participant.id, stage_id=stage.id, lat=53.0, lon=158.0
    )
    coords = (gps.lat, gps.lon)
    await RaceRouteImportService(db_session).save(
        [line()],
        [
            {
                "stage_id": stage.id,
                "reverse": False,
                "direction_confirmed": True,
                "kinds": ["start", "finish"],
            }
        ],
        admin_id=admin.id,
        file_hash="weather",
    )
    assert (await db_session.get(Checkpoint, start.id)).lat == 53
    assert (await db_session.get(Checkpoint, finish.id)).lat == 53.01
    assert (await db_session.get(OfficialMark, mark.id)).checkpoint_id == start.id
    assert (gps.lat, gps.lon) == coords
    assert gps.km_from_start == 0
    assert len(list(await db_session.scalars(select(Checkpoint)))) == 2


async def test_moving_one_stage_shifts_following_checkpoint_distance(
    db_session,
    create_admin,
    create_season,
    create_stage,
    create_checkpoint,
):
    """Изменение длины одного этапа сдвигает километраж следующих КП без их пересоздания"""
    db_session.sync_session.expire_on_commit = False
    admin = await create_admin()
    season = await create_season()
    first = await create_stage(season_id=season.id, order_index=1, distance_km=10)
    second = await create_stage(season_id=season.id, number=2, order_index=2)
    cp = await create_checkpoint(stage_id=second.id, km_from_race_start=15)
    await RaceRouteImportService(db_session).save(
        [line()],
        [
            {
                "stage_id": first.id,
                "reverse": False,
                "direction_confirmed": True,
                "kinds": ["start", "finish"],
            }
        ],
        admin_id=admin.id,
        file_hash="weather",
    )
    await db_session.refresh(cp)
    assert cp.km_from_race_start == pytest.approx(first.distance_km + 5)


async def test_finished_stage_cannot_be_rewritten(
    db_session,
    create_admin,
    create_season,
    create_stage,
):
    """Завершённый этап нельзя переписать погодным импортом"""
    admin = await create_admin()
    season = await create_season()
    stage = await create_stage(season_id=season.id)
    stage.status = "finished"
    await db_session.flush()
    with pytest.raises(HTTPException) as error:
        await RaceRouteImportService(db_session).save(
            [line()],
            [
                {
                    "stage_id": stage.id,
                    "reverse": False,
                    "direction_confirmed": True,
                    "kinds": ["start", "finish"],
                }
            ],
            admin_id=admin.id,
            file_hash="x",
        )
    assert error.value.status_code == 409
