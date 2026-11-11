from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import NotificationQueue
from app.enums import NotificationEventType
from app.services.notifications import NotificationService

DATA_TIME = datetime(2026, 10, 17, 12, 34, tzinfo=UTC)


def _service() -> tuple[NotificationService, MagicMock, NotificationQueue]:
    session = MagicMock(spec=AsyncSession)
    service = NotificationService(session)
    notification = NotificationQueue(id=1, user_id=7)
    service.queue.enqueue = AsyncMock(return_value=notification)
    service.queue.count_sent_last_hour = AsyncMock(return_value=0)
    service.queue.count_sent_last_day = AsyncMock(return_value=0)
    service.queue.mark_skipped = AsyncMock()
    return service, session, notification


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sent_hour", "sent_day", "reason"),
    [
        (0, 0, None),
        (1, 9, None),
        (2, 9, "limit_per_hour"),
        (1, 10, "limit_per_day"),
        (2, 10, "limit_per_hour"),
    ],
)
async def test_enqueue_applies_limits_and_commits(
    monkeypatch: pytest.MonkeyPatch,
    sent_hour: int,
    sent_day: int,
    reason: str | None,
) -> None:
    """Часовой и суточный лимиты определяют пропуск, а операция коммитится"""
    monkeypatch.setattr(
        "app.services.notifications.settings",
        SimpleNamespace(NOTIFICATION_RATE_LIMIT_PER_HOUR=2, NOTIFICATION_RATE_LIMIT_PER_DAY=10),
    )
    service, session, notification = _service()
    service.queue.count_sent_last_hour.return_value = sent_hour
    service.queue.count_sent_last_day.return_value = sent_day

    await service.enqueue(
        user_id=7,
        event_type=NotificationEventType.STAGE_START,
        title="Старт",
        body="Этап начался",
        data_time=DATA_TIME,
    )

    service.queue.enqueue.assert_awaited_once_with(
        user_id=7,
        event_type=NotificationEventType.STAGE_START,
        title="Старт",
        body="Этап начался (данные на 12:34)",
    )
    service.queue.count_sent_last_hour.assert_awaited_once_with(7)
    service.queue.count_sent_last_day.assert_awaited_once_with(7)
    if reason is None:
        service.queue.mark_skipped.assert_not_awaited()
    else:
        service.queue.mark_skipped.assert_awaited_once_with(notification, reason)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_uses_current_utc_time_when_data_time_is_missing() -> None:
    """При отсутствии времени данных текст использует текущее время UTC"""
    service, _, _ = _service()
    before = datetime.now(tz=UTC)

    await service.enqueue(
        user_id=7,
        event_type=NotificationEventType.STAGE_FINISH,
        title="Финиш",
        body="Этап завершён",
    )

    after = datetime.now(tz=UTC)
    body = service.queue.enqueue.await_args.kwargs["body"]
    assert body in {
        f"Этап завершён (данные на {before:%H:%M})",
        f"Этап завершён (данные на {after:%H:%M})",
    }


@pytest.mark.asyncio
async def test_enqueue_failure_does_not_commit() -> None:
    """Ошибка постановки в очередь не приводит к коммиту транзакции"""
    service, session, _ = _service()
    service.queue.enqueue.side_effect = RuntimeError("queue unavailable")

    with pytest.raises(RuntimeError, match="queue unavailable"):
        await service.enqueue(
            user_id=7,
            event_type=NotificationEventType.STAGE_START,
            title="Старт",
            body="Этап начался",
            data_time=DATA_TIME,
        )

    service.queue.count_sent_last_hour.assert_not_awaited()
    service.queue.mark_skipped.assert_not_awaited()
    session.commit.assert_not_awaited()
