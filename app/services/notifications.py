"""Сервис уведомлений: очередь, лимиты, шаблоны.

Лимиты VK: 2/час, 10/сутки. Формулировки содержат время данных
(«данные на HH:MM»), не «прямо сейчас».
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import NotificationEventType
from app.repositories.notification_queue import NotificationQueueRepository

logger = logging.getLogger("avacha.notifications")
settings = get_settings()


class NotificationService:
    """Бизнес-логика уведомлений: очередь, лимиты, тексты."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.queue = NotificationQueueRepository(session)

    async def enqueue(
        self,
        *,
        user_id: int,
        event_type: NotificationEventType,
        title: str,
        body: str,
        data_time: datetime | None = None,
    ) -> None:
        """Поставить уведомление в очередь с проверкой лимитов.

        Если лимит превышен — уведомление всё равно создаётся,
        но со статусом SKIPPED (не отправится).
        """
        if data_time is None:
            data_time = datetime.now(tz=UTC)

        # Обязательная подпись «данные на HH:MM» — не «прямо сейчас».
        body_with_time = f"{body} (данные на {data_time:%H:%M})"

        notification = await self.queue.enqueue(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body_with_time,
        )

        sent_hour = await self.queue.count_sent_last_hour(user_id)
        sent_day = await self.queue.count_sent_last_day(user_id)

        if sent_hour >= settings.NOTIFICATION_RATE_LIMIT_PER_HOUR:
            await self.queue.mark_skipped(notification, "limit_per_hour")
            logger.info("notification_skipped_hourly", extra={"user_id": user_id})
        elif sent_day >= settings.NOTIFICATION_RATE_LIMIT_PER_DAY:
            await self.queue.mark_skipped(notification, "limit_per_day")
            logger.info("notification_skipped_daily", extra={"user_id": user_id})

        await self.session.commit()
