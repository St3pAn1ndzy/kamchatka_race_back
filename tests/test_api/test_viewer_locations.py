"""Тесты публичного API зрительских локаций."""


async def test_list_empty(client) -> None:
    """Нет локаций → пустой массив."""
    response = await client.get("/api/v1/content/viewer-locations")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_with_data_and_kind_order(client, create_viewer_location) -> None:
    """Сортировка: start → finish → viewpoint → festival → other."""
    await create_viewer_location(name="Смотровая", kind="viewpoint")
    await create_viewer_location(name="Старт", kind="start")
    await create_viewer_location(name="Финиш", kind="finish")
    await create_viewer_location(name="Фестиваль", kind="festival")

    response = await client.get("/api/v1/content/viewer-locations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    assert [d["kind"] for d in data] == ["start", "finish", "viewpoint", "festival"]


async def test_filter_by_kind(client, create_viewer_location) -> None:
    """?kind=start отдаёт только старты."""
    await create_viewer_location(name="Старт 1", kind="start")
    await create_viewer_location(name="Старт 2", kind="start")
    await create_viewer_location(name="Финиш", kind="finish")

    response = await client.get("/api/v1/content/viewer-locations?kind=start")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(d["kind"] == "start" for d in data)


async def test_excludes_non_public(client, create_viewer_location) -> None:
    """is_public=False не попадает в публичный список."""
    await create_viewer_location(name="Публичная", kind="start", is_public=True)
    await create_viewer_location(name="Черновик", kind="start", is_public=False)

    response = await client.get("/api/v1/content/viewer-locations")
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Публичная"


async def test_limit_offset(client, create_viewer_location) -> None:
    """Пагинация работает."""
    for i in range(5):
        await create_viewer_location(name=f"Локация {i}", kind="viewpoint")

    response = await client.get("/api/v1/content/viewer-locations?limit=2&offset=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_response_fields(client, create_viewer_location) -> None:
    """Проверка, что поля соответствуют контракту."""
    await create_viewer_location(name="Старт", kind="start")

    response = await client.get("/api/v1/content/viewer-locations")
    item = response.json()[0]

    # Обязательные поля
    assert "id" in item
    assert "name" in item
    assert "kind" in item
    assert "lat" in item
    assert "lon" in item
    assert "safety_notes" in item

    # Поля, которых НЕ должно быть (внутренние)
    assert "stage_id" not in item
    assert "is_public" not in item
    assert "created_at" not in item
    assert "updated_at" not in item


async def test_viewer_locations_have_glyph_field(
    client, db_session, create_viewer_location
) -> None:
    """В ответе /api/v1/content/viewer-locations у каждой локации есть glyph."""
    await create_viewer_location(
        name="Главная сцена", kind="festival", category="stages", glyph="mic"
    )
    await create_viewer_location(name="Фудкорт", kind="festival", category="food", glyph="food")

    response = await client.get("/api/v1/content/viewer-locations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    glyphs = {item["name"]: item["glyph"] for item in data}
    assert glyphs == {"Главная сцена": "mic", "Фудкорт": "food"}


async def test_viewer_locations_glyph_survives_cache(
    client, db_session, create_viewer_location
) -> None:
    """glyph корректно сериализуется в кэш и восстанавливается из него."""
    await create_viewer_location(name="Фудкорт", kind="festival", category="food", glyph="food")

    # Первый запрос — из БД, заполняет кэш
    first = await client.get("/api/v1/content/viewer-locations")
    assert first.status_code == 200
    assert first.json()[0]["glyph"] == "food"

    # Второй запрос — из кэша
    second = await client.get("/api/v1/content/viewer-locations")
    assert second.json()[0]["glyph"] == "food"
