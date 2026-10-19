from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import NotificationQueue
from app.enums import NotificationEventType, NotificationStatus
from app.repositories.notification_queue import NotificationQueueRepository


def _repo() -> tuple[NotificationQueueRepository, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    return NotificationQueueRepository(session), session


def _result(*, items: list[NotificationQueue] | None = None, count: int = 0) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one.return_value = count
    return result


@pytest.mark.asyncio
async def test_enqueue_sets_pending_and_flushes_without_committing() -> None:
    """Новое уведомление получает статус ожидания и flush без коммита"""
    repo, session = _repo()
    scheduled_at = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)

    notification = await repo.enqueue(
        user_id=7,
        event_type=NotificationEventType.STAGE_START,
        title="Старт",
        body="Этап начался",
        scheduled_at=scheduled_at,
    )

    assert session.add.call_args.args[0] is notification
    assert notification.user_id == 7
    assert notification.event_type == NotificationEventType.STAGE_START.value
    assert notification.status == NotificationStatus.PENDING.value
    assert notification.scheduled_at == scheduled_at
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_pending_filters_due_records_and_orders_them() -> None:
    """Выбираются только наступившие уведомления с сортировкой по времени"""
    repo, session = _repo()
    notification = NotificationQueue(id=1)
    session.execute.return_value = _result(items=[notification])
    before = datetime.now(tz=UTC)

    items = await repo.get_pending(limit=5)

    after = datetime.now(tz=UTC)
    assert items == [notification]
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "notification_queue.status = " in sql
    assert "notification_queue.scheduled_at <= " in sql
    assert "ORDER BY notification_queue.scheduled_at" in sql
    assert "LIMIT" in sql
    assert NotificationStatus.PENDING.value in compiled.params.values()
    assert 5 in compiled.params.values()
    query_time = next(value for value in compiled.params.values() if isinstance(value, datetime))
    assert before <= query_time <= after


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "window"),
    [
        ("count_sent_last_hour", timedelta(hours=1)),
        ("count_sent_last_day", timedelta(days=1)),
    ],
)
async def test_sent_counts_are_scoped_to_user_status_and_window(
    method: str, window: timedelta
) -> None:
    """Часовой и суточный счётчики учитывают пользователя, статус и интервал"""
    repo, session = _repo()
    session.execute.return_value = _result(count=3)
    before = datetime.now(tz=UTC)

    count = await getattr(repo, method)(7)

    after = datetime.now(tz=UTC)
    assert count == 3
    compiled = session.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "notification_queue.user_id = " in sql
    assert "notification_queue.status = " in sql
    assert "notification_queue.sent_at >= " in sql
    assert 7 in compiled.params.values()
    assert NotificationStatus.SENT.value in compiled.params.values()
    since = next(value for value in compiled.params.values() if isinstance(value, datetime))
    assert before - window <= since <= after - window


@pytest.mark.asyncio
async def test_mark_sent_records_utc_time_and_flushes() -> None:
    """Отправка отмечается временем UTC и сохраняется через flush"""
    repo, session = _repo()
    notification = NotificationQueue(id=1, status=NotificationStatus.PENDING.value)
    before = datetime.now(tz=UTC)

    await repo.mark_sent(notification)

    assert notification.status == NotificationStatus.SENT.value
    assert before <= notification.sent_at <= datetime.now(tz=UTC)
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "status", "reason", "attempts"),
    [
        ("mark_skipped", NotificationStatus.SKIPPED, "limit_per_hour", 0),
        ("mark_failed", NotificationStatus.FAILED, "vk_send_failed", 1),
    ],
)
async def test_mark_skipped_or_failed_records_reason(
    method: str, status: NotificationStatus, reason: str, attempts: int
) -> None:
    """Пропуск и ошибка записывают причину, статус и число попыток"""
    repo, session = _repo()
    notification = NotificationQueue(id=1, attempts=0, status=NotificationStatus.PENDING.value)

    await getattr(repo, method)(notification, reason)

    assert notification.status == status.value
    assert notification.error_text == reason
    assert notification.attempts == attempts
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_by_user_paginates_newest_first() -> None:
    """История пользователя возвращается по страницам от новых записей"""
    repo, session = _repo()
    notification = NotificationQueue(id=1)
    session.execute.return_value = _result(items=[notification])

    assert await repo.list_by_user(7, limit=20, offset=5) == [notification]

    compiled = session.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "notification_queue.user_id = " in sql
    assert "ORDER BY notification_queue.created_at DESC" in sql
    assert 7 in compiled.params.values()
    assert 20 in compiled.params.values()
    assert 5 in compiled.params.values()


@pytest.mark.asyncio
async def test_count_by_user_excludes_other_users() -> None:
    """Подсчёт уведомлений ограничен указанным пользователем"""
    repo, session = _repo()
    session.execute.return_value = _result(count=4)

    assert await repo.count_by_user(7) == 4

    compiled = session.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    assert "notification_queue.user_id = " in str(compiled)
    assert 7 in compiled.params.values()
