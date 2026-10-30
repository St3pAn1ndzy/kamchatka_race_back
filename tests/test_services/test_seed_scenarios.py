"""Проверки профилей seed через полный запуск main в тестовом SAVEPOINT"""

import json
from contextlib import asynccontextmanager
from fnmatch import fnmatchcase
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, func, select

from app.db.models import (
    Checkpoint,
    Device,
    OfficialMark,
    RaceStatus,
    Season,
    Stage,
    StageRoutePoint,
    TrackPoint,
)
from scripts import seed_mock as seed


@pytest.fixture
def seed_main(db_session, monkeypatch):
    """Подменяет только окружение и внешние эффекты без подмены логики seed"""

    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr(seed, "async_session_factory", factory)
    monkeypatch.setattr(seed, "settings", SimpleNamespace(ENV="dev"))
    monkeypatch.setattr(seed, "_copy_seed_media", lambda *args: None)
    monkeypatch.setattr(seed.cache, "invalidate_pattern", AsyncMock())
    monkeypatch.setattr(db_session.sync_session, "expire_on_commit", False)

    async def run(scenario="standard", **kwargs):
        await seed.main(
            reset=False,
            users_count=2,
            no_track=kwargs.pop("no_track", False),
            force=False,
            scenario=scenario,
            **kwargs,
        )

    return run


async def count(session, model):
    """Считает сохранённые строки модели в тестовой транзакции"""
    return await session.scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize(("scenario", "total"), [("standard", 6), ("overview", 3)])
async def test_live_profiles_have_routes_gps_marks_and_demo_sos(
    db_session, seed_main, scenario, total
):
    """Обычный и обзорный профили создают живые данные и SOS трекеров 3 и 8"""
    await seed_main(scenario)
    stages = list(await db_session.scalars(select(Stage).order_by(Stage.number)))
    assert [s.number for s in stages] == list(range(1, total + 1))
    assert stages[0].status == "active"
    assert stages[0].results_publication == "provisional"
    assert await count(db_session, Checkpoint) == total * 4
    assert await count(db_session, StageRoutePoint) > 0
    assert await count(db_session, TrackPoint) == 300
    assert await count(db_session, OfficialMark) == 30
    assert set(
        await db_session.scalars(select(Device.iridium_number).where(Device.sos_active))
    ) == {"003", "008"}
    race = await db_session.scalar(select(RaceStatus))
    assert race.status == "live" and race.current_stage_id == stages[0].id


async def test_route_import_needs_no_json_and_has_no_live_or_route_data(
    db_session, seed_main, monkeypatch, tmp_path
):
    """Профиль импорта создаёт шесть черновых этапов без геометрии КП GPS и отметок"""
    monkeypatch.setattr(seed, "ROUTE_JSON_PATH", tmp_path / "missing.json")
    await seed_main("route-import")
    stages = list(await db_session.scalars(select(Stage).order_by(Stage.number)))
    assert [s.number for s in stages] == list(range(1, 7))
    assert all(s.status == "planned" and s.results_publication == "draft" for s in stages)
    for model in (StageRoutePoint, Checkpoint, TrackPoint, OfficialMark):
        assert await count(db_session, model) == 0
    assert await count(db_session, Device) == 15
    assert not list(await db_session.scalars(select(Device.id).where(Device.sos_active)))
    race = await db_session.scalar(select(RaceStatus))
    assert race.status == "upcoming" and race.current_stage_id is None


async def test_overview_needs_only_three_geometries_and_overrides_no_track(
    db_session, seed_main, monkeypatch, tmp_path
):
    """Обзор использует только три геометрии и всегда создаёт полные живые данные"""
    data = json.loads(seed.ROUTE_JSON_PATH.read_text())
    data["stages"] = data["stages"][:3]
    file = tmp_path / "three.json"
    file.write_text(json.dumps(data))
    monkeypatch.setattr(seed, "ROUTE_JSON_PATH", file)
    await seed_main("overview", no_track=True)
    assert await count(db_session, Stage) == 3
    assert await count(db_session, TrackPoint) == 300
    assert await count(db_session, OfficialMark) == 30


@pytest.mark.parametrize("scenario", ["overview", "route-import"])
async def test_explicit_profile_repeat_keeps_stage_ids(db_session, seed_main, scenario):
    """Повторный запуск того же профиля сохраняет все поля и идентификаторы этапов"""
    await seed_main(scenario)
    before = (await db_session.execute(select(Stage.__table__).order_by(Stage.id))).all()
    await seed_main(scenario)
    after = (await db_session.execute(select(Stage.__table__).order_by(Stage.id))).all()
    assert after == before


@pytest.mark.parametrize(
    ("initial", "requested"),
    [("standard", "overview"), ("overview", "route-import"), ("route-import", "overview")],
)
async def test_incompatible_profiles_fail_before_any_writes(
    db_session, seed_main, initial, requested
):
    """Несовместимый профиль требует reset до любых INSERT UPDATE или DELETE"""
    await seed_main(initial)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().upper())

    connection = await db_session.connection()
    event.listen(connection.sync_connection, "before_cursor_execute", record)
    try:
        with pytest.raises(ValueError, match="пересоздайте с --reset"):
            await seed_main(requested)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record)
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)


@pytest.mark.parametrize("status", ["active", "finished"])
async def test_import_rejects_started_stages(db_session, seed_main, status):
    """Начатый или завершённый этап запрещает запуск профиля импорта"""
    await seed_main("route-import")
    stage = await db_session.scalar(select(Stage).where(Stage.number == 1))
    stage.status = status
    await db_session.flush()
    with pytest.raises(ValueError, match="пересоздайте с --reset"):
        await seed_main("route-import")
    assert stage.status == status


@pytest.mark.parametrize("kind", ["gps", "mark"])
async def test_import_rejects_existing_live_data(
    db_session, seed_main, create_track_point, create_checkpoint, create_official_mark, kind
):
    """GPS и судейские отметки требуют пересоздания без удаления существующих данных"""
    await seed_main("route-import")
    device = await db_session.scalar(select(Device).order_by(Device.id).limit(1))
    if kind == "gps":
        row = await create_track_point(
            participant_id=device.participant_id, stage_id=device.stage_id, device_id=device.id
        )
        model = TrackPoint
    else:
        cp = await create_checkpoint(stage_id=device.stage_id)
        row = await create_official_mark(participant_id=device.participant_id, checkpoint_id=cp.id)
        model = OfficialMark
    with pytest.raises(ValueError, match="пересоздайте с --reset"):
        await seed_main("route-import")
    assert await db_session.get(model, row.id) is row


async def test_standard_no_track_still_creates_checkpoints(db_session, seed_main):
    """Прежний no_track сохраняет создание КП для стандартного сценария"""
    await seed_main(no_track=True)
    assert await count(db_session, Stage) == 6
    assert await count(db_session, Checkpoint) == 24
    for model in (StageRoutePoint, TrackPoint, OfficialMark):
        assert await count(db_session, model) == 0


async def test_unknown_scenario_rejected_before_seed(db_session, seed_main):
    """Неизвестное имя сценария отклоняется без создания сезона"""
    with pytest.raises(ValueError, match="сценарий"):
        await seed_main("unknown")
    assert await count(db_session, Season) == 0


@pytest.mark.parametrize("scenario", ["standard", "overview", "route-import"])
async def test_seed_clears_public_and_admin_cache_after_commit(
    db_session, seed_main, monkeypatch, scenario
):
    """После успешного commit удаляются устаревшие публичные и административные счётчики"""
    cached = {"public:stages:old": 99, "admin:dashboard:stats": 99, "unrelated:key": 1}
    committed = False
    original_commit = db_session.commit

    async def commit():
        nonlocal committed
        await original_commit()
        committed = True

    async def invalidate(pattern):
        assert committed
        for key in list(cached):
            if fnmatchcase(key, pattern):
                del cached[key]

    monkeypatch.setattr(db_session, "commit", commit)
    monkeypatch.setattr(seed.cache, "invalidate_pattern", invalidate)
    await seed_main(scenario)
    assert committed
    assert cached == {"unrelated:key": 1}


async def test_failed_commit_does_not_invalidate_cache(db_session, seed_main, monkeypatch):
    """При неудачном commit кэш не сбрасывается"""
    monkeypatch.setattr(db_session, "commit", AsyncMock(side_effect=RuntimeError("commit failed")))
    with pytest.raises(RuntimeError, match="commit failed"):
        await seed_main("route-import")
    seed.cache.invalidate_pattern.assert_not_awaited()
