from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_participant_repo
from app.api.v1 import participants as participants_router
from app.api.v1.participants import (
    favorite_add,
    favorite_remove,
    get_participant,
    get_supporters,
    list_participants,
    supporters_rating,
)
from app.db.base import get_session
from app.enums import ParticipantStatus
from app.services.cache import cache


def _participant(id: int = 5):
    return SimpleNamespace(
        id=id,
        name="Racer",
        number=12,
        region="Kamchatka",
        discipline_id=2,
        discipline_ref=SimpleNamespace(name="Long"),
        photo_url=None,
        status=ParticipantStatus.REGISTERED,
        dogs_count=8,
        bio="Profile",
    )


async def test_list_participants_passes_filters_and_supporter_count():
    """Список передаёт фильтры репозиторию и показывает число болельщиков"""
    participants = AsyncMock()
    participants.list_filtered.return_value = [(_participant(), 3)]
    rows = await list_participants(
        participants,
        search="Race",
        discipline_id=2,
        status_filter=None,
        sort="supporters",
        limit=10,
        offset=20,
    )
    assert rows[0].supporters_count == 3
    assert rows[0].discipline == "Long"
    participants.list_filtered.assert_awaited_once_with(
        search="Race", discipline_id=2, status=None, sort="supporters", limit=10, offset=20
    )


async def test_participant_detail_returns_404_when_missing():
    """Запрос несуществующего участника возвращает 404"""
    participants = AsyncMock()
    participants.get_with_supporters_count.return_value = None
    with pytest.raises(HTTPException) as exc:
        await get_participant(99, participants)
    assert exc.value.status_code == 404


async def test_participant_detail_contains_bio_and_supporters():
    """Карточка содержит биографию и число болельщиков"""
    participants = AsyncMock()
    participants.get_with_supporters_count.return_value = (_participant(), 4)
    detail = await get_participant(5, participants)
    assert detail.bio == "Profile"
    assert detail.supporters_count == 4


async def test_supporters_without_user_does_not_check_favorite():
    """Для гостя счётчик доступен без проверки личной подписки"""
    participants = AsyncMock()
    participants.get_by_id.return_value = _participant()
    fans = AsyncMock()
    fans.count_by_participant.return_value = 5
    response = await get_supporters(5, participants, fans, None)
    assert response.supporters_count == 5
    assert response.is_favorite is False
    fans.is_fan.assert_not_awaited()


async def test_add_favorite_returns_created_flag_and_current_count():
    """Повторная подписка сообщает, что запись не создана повторно"""
    participants = AsyncMock()
    participants.get_by_id.return_value = _participant()
    fans = AsyncMock()
    fans.add.return_value = False
    fans.count_by_participant.return_value = 8
    response = await favorite_add(5, participants, fans, SimpleNamespace(id=42))
    assert response.created is False
    assert response.supporters_count == 8
    fans.add.assert_awaited_once_with(42, 5)


async def test_remove_favorite_returns_current_count():
    """Отписка удаляет связь и возвращает актуальный счётчик"""
    participants = AsyncMock()
    participants.get_by_id.return_value = _participant()
    fans = AsyncMock()
    fans.count_by_participant.return_value = 7
    response = await favorite_remove(5, participants, fans, SimpleNamespace(id=42))
    assert response.created is False
    assert response.supporters_count == 7
    fans.remove.assert_awaited_once_with(42, 5)


@pytest.mark.parametrize("operation", ["add", "remove"])
async def test_favorite_rejects_missing_participant(operation):
    """Подписка и отписка от отсутствующего участника дают 404"""
    participants = AsyncMock()
    participants.get_by_id.return_value = None
    fans = AsyncMock()
    endpoint = favorite_add if operation == "add" else favorite_remove
    with pytest.raises(HTTPException) as exc:
        await endpoint(99, participants, fans, SimpleNamespace(id=42))
    assert exc.value.status_code == 404
    fans.add.assert_not_awaited()
    fans.remove.assert_not_awaited()


async def test_rating_skips_deleted_participants_and_includes_delta():
    """Рейтинг пропускает удалённых участников и показывает прирост за сутки"""
    participants = AsyncMock()
    participants.get_by_id.side_effect = [None, _participant(5)]
    fans = AsyncMock()
    fans.rating.return_value = [(1, 10), (5, 8)]
    fans.delta_24h.return_value = 2
    rows = await supporters_rating(participants, fans, limit=20)
    assert [row.participant_id for row in rows] == [5]
    assert rows[0].delta_24h == 2
    fans.rating.assert_awaited_once_with(limit=20)


async def test_http_rejects_invalid_participant_list_limit():
    """HTTP-маршрут отклоняет нулевой лимит до запроса к репозиторию"""
    app = FastAPI()
    app.include_router(participants_router.router)
    participants = AsyncMock()
    app.dependency_overrides[get_participant_repo] = lambda: participants
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/participants?limit=0")
    assert response.status_code == 422
    participants.list_filtered.assert_not_awaited()


def _make_app(db_session, *, user=None) -> FastAPI:
    """Свежий FastAPI с роутером participants и переопределёнными зависимостями."""
    app = FastAPI()
    app.include_router(participants_router.router)

    async def _session_override():
        yield db_session

    app.dependency_overrides[get_session] = _session_override
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


async def test_favorites_ids_requires_auth(db_session) -> None:
    """Без JWT — 401, фильтр «Мои» скрыт на фронте."""
    app = _make_app(db_session)  # user не переопределён — дефолтный get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/participants/favorites/ids")
    assert response.status_code == 401


async def test_favorites_ids_returns_participant_ids(
    db_session,
    create_user,
    create_participant,
    create_fan_subscription,
) -> None:
    """Возвращает ID участников, на которых подписан пользователь."""
    user = await create_user(vk_user_id=100500)
    p1 = await create_participant(number=1)
    p2 = await create_participant(number=2)
    await create_fan_subscription(user_id=user.id, participant_id=p1.id)
    await create_fan_subscription(user_id=user.id, participant_id=p2.id)

    app = _make_app(db_session, user=user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/participants/favorites/ids")

    assert response.status_code == 200
    data = response.json()
    assert sorted(data["participant_ids"]) == sorted([p1.id, p2.id])


async def test_favorites_ids_empty_for_new_user(db_session, create_user) -> None:
    """Новый пользователь без подписок — пустой массив, не ошибка."""
    user = await create_user(vk_user_id=100501)

    app = _make_app(db_session, user=user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/participants/favorites/ids")

    assert response.status_code == 200
    assert response.json() == {"participant_ids": []}


async def test_favorite_add_invalidates_favorites_cache(
    db_session,
    create_user,
    create_participant,
) -> None:
    """POST /favorite инвалидирует кэш — фронт получит свежие данные."""
    user = await create_user(vk_user_id=100502)
    participant = await create_participant(number=1)

    cache_key = f"public:favorites:user:{user.id}"
    await cache.set(cache_key, [], ttl=300)
    assert await cache.get(cache_key) == []

    app = _make_app(db_session, user=user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/participants/{participant.id}/favorite")

    assert response.status_code == 200
    assert await cache.get(cache_key) is None


async def test_favorite_remove_invalidates_favorites_cache(
    db_session,
    create_user,
    create_participant,
    create_fan_subscription,
) -> None:
    """DELETE /favorite инвалидирует кэш — фронт не увидит отписанного участника."""
    user = await create_user(vk_user_id=100503)
    participant = await create_participant(number=1)
    await create_fan_subscription(user_id=user.id, participant_id=participant.id)

    cache_key = f"public:favorites:user:{user.id}"
    await cache.set(cache_key, [participant.id], ttl=300)

    app = _make_app(db_session, user=user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/participants/{participant.id}/favorite")

    assert response.status_code == 200
    assert await cache.get(cache_key) is None
