# Тесты API: public_directory


async def test_list_stages_ok(client, db_session, create_season, create_stage) -> None:
    """Активный сезон + 2 этапа → 200, оба этапа в ответе, поля корректны."""
    season = await create_season(is_active=True)
    await create_stage(season_id=season.id, number=1, order_index=0, name="Этап 1")
    await create_stage(season_id=season.id, number=2, order_index=1, name="Этап 2")

    response = await client.get("/api/v1/directory/stages")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Этап 1"
    assert data[1]["name"] == "Этап 2"
    assert data[0]["number"] == 1
    assert data[0]["distance_km"] == 100.0
    # публичная схема НЕ содержит tracker_interval_seconds
    assert "tracker_interval_seconds" not in data[0]


async def test_list_stages_filters_by_season(client, create_season, create_stage) -> None:
    """season_id передаём явно — фильтр работает."""
    s2026 = await create_season(year=2026, is_active=False)
    s2027 = await create_season(year=2027, is_active=True)
    await create_stage(season_id=s2026.id, number=1, name="Старый этап")
    await create_stage(season_id=s2027.id, number=1, name="Новый этап")

    response = await client.get(f"/api/v1/directory/stages?season_id={s2026.id}")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Старый этап"


async def test_list_stages_no_active_season(client) -> None:
    """Нет активного сезона → 200, пустой список (не 500)."""
    response = await client.get("/api/v1/directory/stages")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_disciplines_ok(client, create_season, create_discipline) -> None:
    """Активные дисциплины отдаются, сортировка по sort_order."""
    season = await create_season(is_active=True)
    await create_discipline(season_id=season.id, code="middle", name="Средняя", sort_order=1)
    await create_discipline(season_id=season.id, code="long", name="Длинная", sort_order=0)

    response = await client.get("/api/v1/directory/disciplines")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert data[0]["code"] == "long"  # sort_order=0 первый
    assert data[1]["code"] == "middle"
    assert "is_active" not in data[0]  # публичная схема без is_active


async def test_list_disciplines_excludes_inactive(client, create_season, create_discipline) -> None:
    """Деактивированные дисциплины в публичный список не попадают."""
    season = await create_season(is_active=True)
    await create_discipline(season_id=season.id, code="long", is_active=True)
    await create_discipline(season_id=season.id, code="obsolete", is_active=False)

    response = await client.get("/api/v1/directory/disciplines")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "long"


async def test_list_stages_requires_no_auth(client, create_season, create_stage) -> None:
    """Публичный эндпоинт — работает без Authorization header."""
    season = await create_season(is_active=True)
    await create_stage(season_id=season.id)

    # никакого headers=... не передаём — специально
    response = await client.get("/api/v1/directory/stages")
    assert response.status_code == 200
