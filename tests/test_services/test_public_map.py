from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.v1.map import router
from app.db.models.discipline import Discipline
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.db.models.track_point import TrackPoint
from app.repositories.checkpoint import CheckpointRepository
from app.repositories.track_point import TrackPointRepository
from app.schemas.map import MapParticipantsResponse
from app.services.public_map import PublicMapService


def _service(stage: Stage | None = None) -> PublicMapService:
    service = PublicMapService(MagicMock(spec=AsyncSession))
    service.stages.get_by_id = AsyncMock(return_value=stage)
    service.disciplines.list_ordered = AsyncMock(return_value=[])
    service.disciplines.get_by_id = AsyncMock(return_value=None)
    service.participants.list_for_map = AsyncMock(return_value=([], 0))
    service.participants.get_by_id = AsyncMock(return_value=None)
    service.track_points.latest_for_map = AsyncMock(return_value=[])
    service.track_points.participant_ids_for_stage = AsyncMock(return_value=[])
    service.track_points.list_for_map_track = AsyncMock(return_value=([], 0))
    return service


def _point(participant_id: int, recorded_at: datetime, *, confirmed: bool = True) -> TrackPoint:
    return TrackPoint(
        id=participant_id,
        device_id=10,
        participant_id=participant_id,
        stage_id=2,
        lat=53.0,
        lon=158.0,
        recorded_at=recorded_at,
        deduplication_key=f"key-{participant_id}",
        is_confirmed=confirmed,
    )


def test_public_map_routes_validate_stage_and_entry_ids() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    client = TestClient(app)

    # stage_id=0 и negative невалидны (Query(gt=0))
    assert client.get("/api/v1/map/participants?stage_id=0").status_code == 422
    assert client.get("/api/v1/map/entry/0/track?stage_id=2").status_code == 422
    assert client.get("/api/v1/map/entry/1/track?stage_id=2&limit=2001").status_code == 422

    paths = app.openapi()["paths"]
    assert all(
        "get" in paths[path]
        for path in (
            "/api/v1/map/participants",
            "/api/v1/map/entry/{entry_id}/track",
        )
    )
    assert "/api/v1/map/checkpoints" not in paths


def test_participants_endpoint_is_public(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    service = MagicMock()
    service.get_participants = AsyncMock(
        return_value=MapParticipantsResponse(stage_id=2, items=[], total=0, limit=500, offset=0)
    )
    monkeypatch.setattr("app.api.v1.map.PublicMapService", lambda _: service)

    response = TestClient(app).get("/api/v1/map/participants?stage_id=2")

    assert response.status_code == 200
    assert response.json() == {"stage_id": 2, "items": [], "total": 0, "limit": 500, "offset": 0}
    service.get_participants.assert_awaited_once_with(2, limit=500, offset=0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("age_seconds", "expected_status"),
    [(100, "fresh"), (1300, "delayed"), (2500, "stale")],
)
async def test_participants_include_no_signal_and_only_public_fields(
    age_seconds: int, expected_status: str
) -> None:
    stage = Stage(id=2, name="Stage", season_id=1, tracker_interval_seconds=1200)
    discipline = Discipline(id=3, season_id=1, code="ski", name="Ski")
    first = Participant(id=1, name="One", number=11, discipline_id=3, status="active")
    second = Participant(id=2, name="Two", number=12, discipline_id=3, status="registered")
    first.discipline_ref = discipline
    second.discipline_ref = discipline
    service = _service(stage)
    service.disciplines.list_ordered.return_value = [discipline]
    service.participants.list_for_map.return_value = ([first, second], 2)
    service.track_points.latest_for_map.return_value = [
        _point(1, datetime.now(tz=UTC) - timedelta(seconds=age_seconds))
    ]

    response = await service.get_participants(2, limit=500, offset=0)

    assert response.total == 2
    assert [item.freshness_status for item in response.items] == [expected_status, "no_data"]
    assert response.items[0].position.lat == 53.0
    assert response.items[1].position is None
    assert "device_id" not in response.model_dump_json()
    assert "sos_active" not in response.model_dump_json()
    service.track_points.latest_for_map.assert_awaited_once_with(2, [1, 2])


@pytest.mark.asyncio
async def test_track_rejects_participant_from_another_season() -> None:
    service = _service(Stage(id=2, name="Stage", season_id=1))
    service.participants.get_by_id.return_value = Participant(
        id=5, name="Other", number=5, discipline_id=3
    )
    service.disciplines.get_by_id.return_value = Discipline(
        id=3, season_id=9, code="ski", name="Ski"
    )

    with pytest.raises(HTTPException) as error:
        await service.get_track(2, 5, limit=500, offset=0)

    assert error.value.status_code == 404
    service.track_points.list_for_map_track.assert_not_awaited()


@pytest.mark.asyncio
async def test_track_is_chronological_and_paginated() -> None:
    service = _service(Stage(id=2, name="Stage", season_id=1))
    service.participants.get_by_id.return_value = Participant(
        id=5, name="Racer", number=5, discipline_id=3
    )
    service.disciplines.get_by_id.return_value = Discipline(
        id=3, season_id=1, code="ski", name="Ski"
    )
    point = _point(5, datetime(2026, 10, 15, tzinfo=UTC))
    service.track_points.list_for_map_track.return_value = ([point], 12)

    response = await service.get_track(2, 5, limit=1, offset=3)

    assert response.total == 12
    assert response.limit == 1
    assert response.offset == 3
    assert len(response.points) == 1
    service.track_points.list_for_map_track.assert_awaited_once_with(2, 5, limit=1, offset=3)


@pytest.mark.asyncio
async def test_map_queries_filter_confirmation_stage_and_visibility() -> None:
    session = MagicMock(spec=AsyncSession)
    tracks = TrackPointRepository(session)
    checkpoints = CheckpointRepository(session)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    await tracks.latest_for_map(2, [5])
    latest_stmt = session.execute.await_args.args[0]
    latest_sql = str(latest_stmt.compile(dialect=postgresql.dialect()))
    assert "row_number() OVER" in latest_sql
    assert "track_points.is_confirmed IS true" in latest_sql
    assert "track_points.stage_id" in latest_sql

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    session.execute = AsyncMock(side_effect=[count_result, result])
    await tracks.list_for_map_track(2, 5, limit=20, offset=10)
    count_stmt = session.execute.await_args_list[0].args[0]
    history_stmt = session.execute.await_args_list[1].args[0]
    count_sql = str(count_stmt.compile(dialect=postgresql.dialect()))
    history_sql = str(history_stmt.compile(dialect=postgresql.dialect()))
    assert "track_points.is_confirmed IS true" in count_sql
    assert "track_points.is_confirmed IS true" in history_sql
    assert "track_points.participant_id" in history_sql
    assert "ORDER BY track_points.recorded_at, track_points.id" in history_sql

    session.execute = AsyncMock(return_value=result)
    await checkpoints.list_public_for_stage(2)
    checkpoint_stmt = session.execute.await_args.args[0]
    checkpoint_sql = str(checkpoint_stmt.compile(dialect=postgresql.dialect()))
    assert "checkpoints.is_public IS true" in checkpoint_sql
    assert "checkpoints.stage_id" in checkpoint_sql


async def test_get_route_geojson_ok(
    db_session, create_season, create_stage, create_route_point
) -> None:
    """GeoJSON имеет правильную структуру и порядок координат [lon, lat]."""
    season = await create_season(is_active=True)
    stage = await create_stage(season_id=season.id)

    await create_route_point(stage_id=stage.id, position=0, lat=55.1, lon=160.1)
    await create_route_point(stage_id=stage.id, position=1, lat=55.2, lon=160.2)
    await create_route_point(stage_id=stage.id, position=2, lat=55.3, lon=160.3)

    service = PublicMapService(db_session)
    result = await service.get_stage_route_geojson(stage.id)

    assert result.type == "LineString"
    assert len(result.coordinates) == 3
    assert result.coordinates[0] == [160.1, 55.1]
    assert result.coordinates[2] == [160.3, 55.3]


async def test_get_route_geojson_empty_returns_none(
    db_session, create_season, create_stage
) -> None:
    """Пустой маршрут → сервис возвращает None (не кидает HTTPException)."""
    season = await create_season(is_active=True)
    stage = await create_stage(season_id=season.id)

    service = PublicMapService(db_session)
    result = await service.get_stage_route_geojson(stage.id)

    assert result is None


async def test_get_route_geojson_stage_not_found(db_session) -> None:
    """Несуществующий этап → 404."""
    from fastapi import HTTPException

    service = PublicMapService(db_session)
    with pytest.raises(HTTPException) as exc:
        await service.get_stage_route_geojson(99999)
    assert exc.value.status_code == 404


async def test_get_positions_returns_latest_point(
    db_session,
    create_discipline,
    create_season,
    create_stage,
    create_participant,
    create_track_point,
    create_checkpoint,
    create_official_mark,
) -> None:
    """Возвращает последнюю точку и last_cp_id."""
    season = await create_season(is_active=True)
    discipline = await create_discipline(season_id=season.id)
    stage = await create_stage(season_id=season.id)
    participant = await create_participant(number=14, name="Иван", discipline_id=discipline.id)
    cp = await create_checkpoint(stage_id=stage.id, kind="start", code="Старт")

    now = datetime.now(tz=UTC)
    # Две точки: старая и новая — должна вернуться только новая
    await create_track_point(
        participant_id=participant.id,
        stage_id=stage.id,
        lat=55.0,
        lon=160.0,
        recorded_at=now - timedelta(minutes=30),
    )
    await create_track_point(
        participant_id=participant.id,
        stage_id=stage.id,
        lat=55.5,
        lon=160.5,
        recorded_at=now,
    )
    # Отметка на КП
    await create_official_mark(participant_id=participant.id, checkpoint_id=cp.id)

    service = PublicMapService(db_session)
    result = await service.get_positions(stage.id)

    assert len(result) == 1
    assert result[0].bib == 14
    assert result[0].lat == 55.5
    assert result[0].last_cp_id == cp.id


async def test_get_positions_since_filter(
    db_session, create_season, create_stage, create_participant, create_track_point
) -> None:
    """?since= отсекает старые точки."""
    season = await create_season(is_active=True)
    stage = await create_stage(season_id=season.id)
    participant = await create_participant(number=14)

    now = datetime.now(tz=UTC)
    await create_track_point(
        participant_id=participant.id,
        stage_id=stage.id,
        recorded_at=now - timedelta(hours=2),
    )

    service = PublicMapService(db_session)
    # since на 1 час назад — точка старая, должна быть отброшена
    result = await service.get_positions(stage.id, since=now - timedelta(hours=1))
    assert result == []
