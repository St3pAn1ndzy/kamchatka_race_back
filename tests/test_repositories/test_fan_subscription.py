"""Тесты репозитория подписок «Болею за»."""

from datetime import UTC, datetime, timedelta

from app.repositories.fun_subscription import FanSubscriptionRepository


async def test_add_creates_subscription(db_session, create_user, create_participant) -> None:
    """Первый add создаёт запись и возвращает True."""
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    created = await repo.add(user.id, participant.id)

    assert created is True
    assert await repo.is_fan(user.id, participant.id) is True


async def test_add_idempotent(db_session, create_user, create_participant) -> None:
    """Повторный add не создаёт дубликат и возвращает False."""
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    first = await repo.add(user.id, participant.id)
    second = await repo.add(user.id, participant.id)
    third = await repo.add(user.id, participant.id)

    assert first is True
    assert second is False
    assert third is False
    assert await repo.count_by_participant(participant.id) == 1


async def test_add_different_users(db_session, create_user, create_participant) -> None:
    """Разные пользователи могут подписаться на одного участника."""
    user1 = await create_user()
    user2 = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user1.id, participant.id)
    await repo.add(user2.id, participant.id)

    assert await repo.count_by_participant(participant.id) == 2


async def test_remove_deletes_subscription(db_session, create_user, create_participant) -> None:
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user.id, participant.id)

    removed = await repo.remove(user.id, participant.id)
    assert removed is True
    assert await repo.is_fan(user.id, participant.id) is False
    assert await repo.count_by_participant(participant.id) == 0


async def test_remove_nonexistent_returns_false(
    db_session, create_user, create_participant
) -> None:
    """remove несуществующей подписки не падает, возвращает False."""
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    assert await repo.remove(user.id, participant.id) is False


async def test_remove_idempotent(db_session, create_user, create_participant) -> None:
    """Двойной remove: первый True, второй False."""
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user.id, participant.id)

    first = await repo.remove(user.id, participant.id)
    second = await repo.remove(user.id, participant.id)

    assert first is True
    assert second is False


async def test_is_fan_true_when_subscribed(db_session, create_user, create_participant) -> None:
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user.id, participant.id)

    assert await repo.is_fan(user.id, participant.id) is True


async def test_is_fan_false_when_not_subscribed(
    db_session, create_user, create_participant
) -> None:
    user = await create_user()
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    assert await repo.is_fan(user.id, participant.id) is False


async def test_count_by_participant_empty(db_session, create_participant) -> None:
    participant = await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    assert await repo.count_by_participant(participant.id) == 0


async def test_count_by_participant_filters_correctly(
    db_session, create_user, create_participant
) -> None:
    """Считаются только подписки на конкретного участника."""
    user1 = await create_user()
    user2 = await create_user()
    user3 = await create_user()
    p1 = await create_participant(number=1)
    p2 = await create_participant(number=2)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user1.id, p1.id)
    await repo.add(user2.id, p1.id)
    await repo.add(user3.id, p2.id)  # другой участник

    assert await repo.count_by_participant(p1.id) == 2
    assert await repo.count_by_participant(p2.id) == 1


async def test_delta_24h_counts_recent(
    db_session, create_user, create_participant, create_fan_subscription
) -> None:
    """delta_24h считает только подписки за последние 24 часа."""
    participant = await create_participant(number=1)
    user1 = await create_user()
    user2 = await create_user()
    user3 = await create_user()

    now = datetime.now(tz=UTC)
    await create_fan_subscription(
        user_id=user1.id,
        participant_id=participant.id,
        created_at=now - timedelta(hours=1),
    )
    await create_fan_subscription(
        user_id=user2.id,
        participant_id=participant.id,
        created_at=now - timedelta(hours=2),
    )
    await create_fan_subscription(
        user_id=user3.id,
        participant_id=participant.id,
        created_at=now - timedelta(hours=48),
    )

    repo = FanSubscriptionRepository(db_session)
    assert await repo.delta_24h(participant.id) == 2


async def test_delta_24h_zero_when_only_old(
    db_session, create_user, create_participant, create_fan_subscription
) -> None:
    """Если подписки только старые — delta_24h = 0."""
    participant = await create_participant(number=1)
    user = await create_user()

    await create_fan_subscription(
        user_id=user.id,
        participant_id=participant.id,
        created_at=datetime.now(tz=UTC) - timedelta(days=2),
    )

    repo = FanSubscriptionRepository(db_session)
    assert await repo.delta_24h(participant.id) == 0


async def test_rating_orders_by_count_desc(db_session, create_user, create_participant) -> None:
    """Рейтинг отсортирован по убыванию числа болельщиков."""
    p1 = await create_participant(number=1)
    p2 = await create_participant(number=2)
    p3 = await create_participant(number=3)

    repo = FanSubscriptionRepository(db_session)

    # p2 — 3 болельщика, p1 — 2, p3 — 1
    for _ in range(3):
        u = await create_user()
        await repo.add(u.id, p2.id)
    for _ in range(2):
        u = await create_user()
        await repo.add(u.id, p1.id)
    u = await create_user()
    await repo.add(u.id, p3.id)

    rows = await repo.rating(limit=10)

    # Порядок детерминирован, потому что количества разные
    assert rows == [(p2.id, 3), (p1.id, 2), (p3.id, 1)]


async def test_rating_respects_limit(db_session, create_user, create_participant) -> None:
    """limit ограничивает количество строк."""
    repo = FanSubscriptionRepository(db_session)
    for i in range(5):
        p = await create_participant(number=i + 1)
        u = await create_user()
        await repo.add(u.id, p.id)

    rows = await repo.rating(limit=2)
    assert len(rows) == 2


async def test_rating_empty_when_no_subscriptions(db_session, create_participant) -> None:
    """Участники без подписок не попадают в рейтинг."""
    await create_participant(number=1)

    repo = FanSubscriptionRepository(db_session)
    assert await repo.rating(limit=10) == []


async def test_list_participant_ids_empty(db_session, create_user) -> None:
    user = await create_user()

    repo = FanSubscriptionRepository(db_session)
    assert await repo.list_participant_ids_by_user(user.id) == []


async def test_list_participant_ids_returns_all(
    db_session, create_user, create_participant
) -> None:
    """Возвращает ID всех участников, за которых болеет пользователь."""
    user = await create_user()
    p1 = await create_participant(number=1)
    p2 = await create_participant(number=2)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user.id, p1.id)
    await repo.add(user.id, p2.id)

    ids = await repo.list_participant_ids_by_user(user.id)
    # Порядок не гарантирован — сравниваем как множества
    assert set(ids) == {p1.id, p2.id}


async def test_list_participant_ids_isolates_by_user(
    db_session, create_user, create_participant
) -> None:
    """Не возвращает подписки других пользователей."""
    user1 = await create_user()
    user2 = await create_user()
    p1 = await create_participant(number=1)
    p2 = await create_participant(number=2)

    repo = FanSubscriptionRepository(db_session)
    await repo.add(user1.id, p1.id)
    await repo.add(user2.id, p2.id)

    assert await repo.list_participant_ids_by_user(user1.id) == [p1.id]
    assert await repo.list_participant_ids_by_user(user2.id) == [p2.id]
