"""E2E тесты для /api/v1/stages/*."""


async def test_track_endpoint_ok(client, create_season, create_stage, create_route_point) -> None:
    season = await create_season(is_active=True)
    stage = await create_stage(season_id=season.id)
    await create_route_point(stage_id=stage.id, position=0, lat=55.1, lon=160.1)

    response = await client.get(f"/api/v1/stages/{stage.id}/track")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "LineString"
    assert len(data["coordinates"]) == 1
    assert data["coordinates"][0] == [160.1, 55.1]


async def test_track_endpoint_404(client) -> None:
    response = await client.get("/api/v1/stages/99999/track")
    assert response.status_code == 404


async def test_checkpoints_endpoint_ok(
    client, create_season, create_stage, create_checkpoint
) -> None:
    season = await create_season(is_active=True)
    stage = await create_stage(season_id=season.id)
    await create_checkpoint(stage_id=stage.id, kind="start", code="Старт")

    response = await client.get(f"/api/v1/stages/{stage.id}/checkpoints")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["type"] == "start"  # ← алиас kind → type
    assert data[0]["code"] == "Старт"
    assert "km" in data[0]  # ← алиас km_from_race_start → km
    assert "elevation" in data[0]  # ← алиас altitude → elevation


async def test_positions_endpoint_ok(
    client,
    create_season,
    create_discipline,
    create_stage,
    create_participant,
    create_track_point,
    create_checkpoint,
    create_official_mark,
) -> None:
    season = await create_season(is_active=True)
    discipline = await create_discipline(season_id=season.id)
    stage = await create_stage(season_id=season.id)

    participant = await create_participant(number=14, name="Иван", discipline_id=discipline.id)

    cp = await create_checkpoint(stage_id=stage.id, kind="start", code="Старт")

    await create_track_point(participant_id=participant.id, stage_id=stage.id, lat=55.5, lon=160.5)
    await create_official_mark(participant_id=participant.id, checkpoint_id=cp.id)

    response = await client.get(f"/api/v1/stages/{stage.id}/positions")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["bib"] == 14
    assert data[0]["last_cp_id"] == cp.id
