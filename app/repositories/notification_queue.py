"""Репозиторий очереди уведомлений."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db.models.notification import NotificationQueue
from app.enums import NotificationEventType, NotificationStatus
from app.repositories.base import BaseRepository


class NotificationQueueRepository(BaseRepository[NotificationQueue]):
    model = NotificationQueue

    async def enqueue(
        self,
        *,
        user_id: int,
        event_type: NotificationEventType,
        title: str,
        body: str,
        scheduled_at: datetime | None = None,
    ) -> NotificationQueue:
        """Поставить уведомление в очередь."""
        notification = NotificationQueue(
            user_id=user_id,
            event_type=event_type.value,
            title=title,
            body=body,
            status=NotificationStatus.PENDING.value,
            scheduled_at=scheduled_at or datetime.now(tz=UTC),
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get_pending(self, *, limit: int = 100) -> list[NotificationQueue]:
        """Pending-уведомления, готовые к отправке."""
        now = datetime.now(tz=UTC)
        stmt = (
            select(NotificationQueue)
            .where(
                NotificationQueue.status == NotificationStatus.PENDING.value,
                NotificationQueue.scheduled_at <= now,
            )
            .order_by(NotificationQueue.scheduled_at)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_sent_last_hour(self, user_id: int) -> int:
        since = datetime.now(tz=UTC) - timedelta(hours=1)
        stmt = select(func.count(NotificationQueue.id)).where(
            NotificationQueue.user_id == user_id,
            NotificationQueue.status == NotificationStatus.SENT.value,
            NotificationQueue.sent_at >= since,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_sent_last_day(self, user_id: int) -> int:
        since = datetime.now(tz=UTC) - timedelta(days=1)
        stmt = select(func.count(NotificationQueue.id)).where(
            NotificationQueue.user_id == user_id,
            NotificationQueue.status == NotificationStatus.SENT.value,
            NotificationQueue.sent_at >= since,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def mark_sent(self, notification: NotificationQueue) -> None:
        notification.status = NotificationStatus.SENT.value
        notification.sent_at = datetime.now(tz=UTC)
        await self.session.flush()

    async def mark_skipped(self, notification: NotificationQueue, reason: str) -> None:
        notification.status = NotificationStatus.SKIPPED.value
        notification.error_text = reason
        await self.session.flush()

    async def mark_failed(self, notification: NotificationQueue, error: str) -> None:
        notification.status = NotificationStatus.FAILED.value
        notification.attempts += 1
        notification.error_text = error
        await self.session.flush()

    async def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationQueue]:
        stmt = (
            select(NotificationQueue)
            .where(NotificationQueue.user_id == user_id)
            .order_by(NotificationQueue.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        stmt = select(func.count(NotificationQueue.id)).where(NotificationQueue.user_id == user_id)
        return int((await self.session.execute(stmt)).scalar_one())
