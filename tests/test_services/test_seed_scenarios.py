"""Проверки профилей seed через полный запуск main в тестовом SAVEPOINT"""

import json
from contextlib import asynccontextmanager
from fnmatch import fnmatchcase
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import event, func, select

from app.config import Settings
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


def scenario_settings(scenario):
    """Задаёт локальное окружение и отдельные ресурсы выбранного профиля"""
    database, redis_db = {
        "overview": ("avacha_demo_overview", 13),
        "route-import": ("avacha_demo_import", 14),
    }.get(scenario, ("avacha", 0))
    return Settings(
        ENV="dev",
        POSTGRES_HOST="localhost",
        POSTGRES_DB=database,
        REDIS_HOST="127.0.0.1",
        REDIS_DB=redis_db,
    )


@pytest.fixture
def seed_main(db_session, monkeypatch):
    """Подменяет только окружение и внешние эффекты без подмены логики seed"""

    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr(seed, "async_session_factory", factory)
    monkeypatch.setattr(seed, "_copy_seed_media", lambda *args: None)
    monkeypatch.setattr(seed.cache, "invalidate_pattern", AsyncMock())
    monkeypatch.setattr(db_session.sync_session, "expire_on_commit", False)

    async def run(scenario="standard", **kwargs):
        monkeypatch.setattr(seed, "settings", scenario_settings(scenario))
        await seed.main(
            reset=kwargs.pop("reset", False),
            users_count=2,
            no_track=kwargs.pop("no_track", False),
            force=kwargs.pop("force", False),
            scenario=scenario,
            **kwargs,
        )

    return run


@pytest.mark.parametrize("scenario", ["overview", "route-import"])
@pytest.mark.parametrize("reset", [False, True])
@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("database", ["avacha", "avacha_test", "other-profile"])
async def test_explicit_profile_rejects_wrong_database_before_session(
    monkeypatch, scenario, reset, force, database
):
    """Даже reset с force не открывает сессию основной или чужой базы"""
    if database == "other-profile":
        database = "avacha_demo_import" if scenario == "overview" else "avacha_demo_overview"
    monkeypatch.setattr(
        seed, "settings", scenario_settings(scenario).model_copy(update={"POSTGRES_DB": database})
    )
    factory = Mock(side_effect=AssertionError("Сессия не должна открываться"))
    monkeypatch.setattr(seed, "async_session_factory", factory)
    with pytest.raises(ValueError, match="демонстрационн.*баз"):
        await seed.main(reset=reset, users_count=2, no_track=False, force=force, scenario=scenario)
    factory.assert_not_called()


@pytest.mark.parametrize("scenario", ["overview", "route-import"])
@pytest.mark.parametrize(
    "overrides",
    [{"ENV": "prod"}, {"POSTGRES_HOST": "database.example"}, {"REDIS_HOST": "cache.example"}],
)
async def test_explicit_profile_requires_local_dev_even_with_reset_force(
    monkeypatch, scenario, overrides
):
    """Именованная демобаза не разрешает рабочее окружение и удалённые сервисы"""
    monkeypatch.setattr(seed, "settings", scenario_settings(scenario).model_copy(update=overrides))
    factory = Mock(side_effect=AssertionError("Сессия не должна открываться"))
    monkeypatch.setattr(seed, "async_session_factory", factory)
    with pytest.raises(ValueError, match="локальн"):
        await seed.main(reset=True, users_count=2, no_track=False, force=True, scenario=scenario)
    factory.assert_not_called()


@pytest.mark.parametrize("scenario", ["overview", "route-import"])
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
async def test_explicit_profile_accepts_its_local_demo_database(monkeypatch, scenario, host):
    """Корректный профиль проходит защиту до открытия сессии"""
    monkeypatch.setattr(
        seed,
        "settings",
        scenario_settings(scenario).model_copy(update={"POSTGRES_HOST": host, "REDIS_HOST": host}),
    )
    factory = Mock(side_effect=RuntimeError("Открытие сессии"))
    monkeypatch.setattr(seed, "async_session_factory", factory)
    with pytest.raises(RuntimeError, match="Открытие сессии"):
        await seed.main(reset=True, users_count=2, no_track=False, force=True, scenario=scenario)
    factory.assert_called_once_with()


@pytest.mark.parametrize(("environment", "force"), [("dev", False), ("prod", True)])
async def test_standard_keeps_existing_environment_rules(monkeypatch, environment, force):
    """Стандартный запуск сохраняет поддержку основной базы и прежнего force"""
    monkeypatch.setattr(
        seed,
        "settings",
        scenario_settings("standard").model_copy(
            update={"ENV": environment, "POSTGRES_HOST": "postgres", "REDIS_HOST": "redis"}
        ),
    )
    factory = Mock(side_effect=RuntimeError("Открытие сессии"))
    monkeypatch.setattr(seed, "async_session_factory", factory)
    with pytest.raises(RuntimeError, match="Открытие сессии"):
        await seed.main(reset=True, users_count=2, no_track=False, force=force)
    factory.assert_called_once_with()


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


async def test_overview_to_standard_initializes_only_new_stages(db_session, seed_main):
    """Дополнение до шести этапов сохраняет старые КП и маршрут и допускает повторный запуск"""
    await seed_main("overview")
    stage = await db_session.scalar(select(Stage).where(Stage.number == 2))
    stage.name = "Изменённый этап"
    stage.results_publication = "official"
    cp = await db_session.scalar(select(Checkpoint).where(Checkpoint.stage_id == stage.id).limit(1))
    cp.name = "Изменённый КП"
    cp.lat = 53.123
    point = await db_session.scalar(
        select(StageRoutePoint).where(StageRoutePoint.stage_id == stage.id).limit(1)
    )
    point.lat = 53.456
    await db_session.flush()

    async def snapshot(model, stage_ids=None):
        query = select(model.__table__).order_by(model.id)
        if stage_ids is not None:
            column = model.id if model is Stage else model.stage_id
            query = query.where(column.in_(stage_ids))
        return (await db_session.execute(query)).all()

    models = (Stage, Checkpoint, StageRoutePoint)
    old_ids = list(await db_session.scalars(select(Stage.id)))
    before = [await snapshot(model, old_ids) for model in models]
    await seed_main()
    assert [await snapshot(model, old_ids) for model in models] == before
    stages = list(await db_session.scalars(select(Stage).order_by(Stage.number)))
    assert [s.number for s in stages] == [1, 2, 3, 4, 5, 6]
    route_data = json.loads(seed.ROUTE_JSON_PATH.read_text())["stages"]
    for stage in stages[3:]:
        cps = list(
            await db_session.scalars(
                select(Checkpoint)
                .where(Checkpoint.stage_id == stage.id)
                .order_by(Checkpoint.order_index)
            )
        )
        assert [cp.kind for cp in cps] == ["start", "checkpoint", "checkpoint", "finish"]
        points = list(
            await db_session.scalars(
                select(StageRoutePoint)
                .where(StageRoutePoint.stage_id == stage.id)
                .order_by(StageRoutePoint.position)
            )
        )
        coords = next(data["coordinates"] for data in route_data if data["number"] == stage.number)
        assert [p.position for p in points] == list(range(len(coords)))
        assert [[p.lon, p.lat] for p in points] == coords
        assert [cp.lon for cp in cps] == [
            coords[i][0] for i in (0, int(len(coords) * 0.3), int(len(coords) * 0.7), -1)
        ]
        assert [cp.lat for cp in cps] == [
            coords[i][1] for i in (0, int(len(coords) * 0.3), int(len(coords) * 0.7), -1)
        ]
    complete = [await snapshot(model) for model in models]
    await seed_main()
    assert [await snapshot(model) for model in models] == complete


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


@pytest.mark.parametrize("scenario", ["overview", "route-import"])
async def test_explicit_profile_rejects_shared_cache_before_session(monkeypatch, scenario):
    """Демосид не очищает общий Redis даже при правильном имени базы и reset с force"""
    monkeypatch.setattr(
        seed, "settings", scenario_settings(scenario).model_copy(update={"REDIS_DB": 0})
    )
    factory = Mock(side_effect=AssertionError("Сессия не должна открываться"))
    monkeypatch.setattr(seed, "async_session_factory", factory)
    with pytest.raises(ValueError, match="Redis"):
        await seed.main(reset=True, users_count=2, no_track=False, force=True, scenario=scenario)
    factory.assert_not_called()
