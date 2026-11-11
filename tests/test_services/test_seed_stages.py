"""Дополнение этапов seed без изменения существующих данных"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import event, select

from app.db.models.stage import Stage
from scripts.seed_mock import STAGES_DATA, ensure_stages


def snapshot(row):
    return {column.key: getattr(row, column.key) for column in row.__table__.columns}


@pytest.fixture
async def season_three(create_season, create_stage):
    season = await create_season()
    stages = [
        await create_stage(season_id=season.id, number=n, name=f"Исходный {n}") for n in range(1, 4)
    ]
    return season, stages


async def test_three_to_six_preserves_existing_columns(db_session, season_three):
    """Добавление этапов 4–6 сохраняет все поля существующих этапов и не завершает транзакцию"""
    season, existing = season_three
    existing[0].status = "active"
    existing[0].results_publication = "official"
    existing[0].order_index = 99
    await db_session.flush()
    before = [snapshot(s) for s in existing]
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.upper())

    connection = await db_session.connection()
    event.listen(connection.sync_connection, "before_cursor_execute", record)
    try:
        with patch.object(db_session, "commit", new_callable=AsyncMock) as commit:
            stages = await ensure_stages(db_session, season, STAGES_DATA)
            commit.assert_not_awaited()
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record)
    assert any("SEASONS" in sql and "FOR UPDATE" in sql for sql in statements)
    assert [s.number for s in stages] == list(range(1, 7))
    assert [s.id for s in stages[:3]] == [s.id for s in existing]
    for stage in existing:
        await db_session.refresh(stage)
    assert [snapshot(s) for s in existing] == before
    for stage, data in zip(stages[3:], STAGES_DATA[3:], strict=True):
        assert stage.name == f"Этап {data['number']}. {data['name']}"
        assert stage.distance_km == data["distance"]
        assert stage.order_index == stage.number - 1
        assert stage.status == "planned"
        assert stage.results_publication == "draft"


async def test_repeat_preserves_mapping(db_session, season_three):
    """Повторный запуск сохраняет прежние идентификаторы без дубликатов"""
    season, _ = season_three
    first = await ensure_stages(db_session, season, STAGES_DATA)
    before = [snapshot(s) for s in first]
    second = await ensure_stages(db_session, season, STAGES_DATA)
    assert [snapshot(s) for s in second] == before
    assert len(list(await db_session.scalars(select(Stage.id)))) == 6


async def test_other_season_and_extra_stage_untouched(
    db_session, season_three, create_season, create_stage
):
    """Этапы другого сезона и дополнительные номера не меняются"""
    season, _ = season_three
    other = await create_season(year=2028)
    foreign = await create_stage(season_id=other.id, number=4)
    extra = await create_stage(season_id=season.id, number=9)
    before = [snapshot(foreign), snapshot(extra)]
    stages = await ensure_stages(db_session, season, STAGES_DATA)
    assert [s.number for s in stages] == [1, 2, 3, 4, 5, 6, 9]
    assert all(s.season_id == season.id for s in stages)
    await db_session.refresh(foreign)
    await db_session.refresh(extra)
    assert [snapshot(foreign), snapshot(extra)] == before


async def test_gps_marks_and_related_data_preserved(
    db_session,
    season_three,
    create_participant,
    create_track_point,
    create_checkpoint,
    create_official_mark,
    create_route_point,
):
    """Дополнение этапов не меняет GPS, отметки, КП и существующий маршрут"""
    season, existing = season_three
    participant = await create_participant()
    gps = await create_track_point(participant_id=participant.id, stage_id=existing[0].id)
    cp = await create_checkpoint(stage_id=existing[0].id)
    mark = await create_official_mark(participant_id=participant.id, checkpoint_id=cp.id)
    point = await create_route_point(stage_id=existing[0].id)
    rows = [season, *existing, participant, gps, cp, mark, point]
    before = [snapshot(row) for row in rows]
    await ensure_stages(db_session, season, STAGES_DATA, no_track=True)
    for row in rows:
        await db_session.refresh(row)
    assert [snapshot(row) for row in rows] == before


@pytest.mark.parametrize("no_track", [False, True])
async def test_new_stage_one_status(db_session, create_season, no_track):
    """Режим без треков создаёт этапы, доступные для первичного импорта KML"""
    season = await create_season()
    stages = await ensure_stages(db_session, season, STAGES_DATA, no_track=no_track)
    assert stages[0].status == ("planned" if no_track else "active")
    assert stages[0].results_publication == ("draft" if no_track else "provisional")
    assert all(s.status == "planned" and s.results_publication == "draft" for s in stages[1:])


async def test_no_track_preserves_existing_active_stage(db_session, season_three):
    """Режим без треков не сбрасывает статус уже существующего этапа"""
    season, existing = season_three
    existing[0].status = "active"
    existing[0].results_publication = "provisional"
    await db_session.flush()
    before = snapshot(existing[0])
    await ensure_stages(db_session, season, STAGES_DATA, no_track=True)
    await db_session.refresh(existing[0])
    assert snapshot(existing[0]) == before


@pytest.mark.parametrize("number", [0, -1, 2, 9])
async def test_invalid_existing_numbers_rejected_before_inserts(
    db_session, season_three, create_stage, number
):
    """Некорректные номера в базе отклоняются до добавления новых этапов"""
    season, _ = season_three
    await create_stage(season_id=season.id, number=number)
    if number == 9:
        await create_stage(season_id=season.id, number=9)
    before = list(await db_session.scalars(select(Stage.id).order_by(Stage.id)))
    with pytest.raises(ValueError, match="номер"):
        await ensure_stages(db_session, season, STAGES_DATA)
    assert list(await db_session.scalars(select(Stage.id).order_by(Stage.id))) == before


@pytest.mark.parametrize("numbers", [[1, 1], [0], [-1]])
async def test_invalid_seed_numbers_rejected(db_session, create_season, numbers):
    """Повторные и неположительные номера в исходных данных отклоняются"""
    season = await create_season()
    data = [dict(STAGES_DATA[0], number=n) for n in numbers]
    with pytest.raises(ValueError, match="номер"):
        await ensure_stages(db_session, season, data)
    assert not list(await db_session.scalars(select(Stage.id)))
