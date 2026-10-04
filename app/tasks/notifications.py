"""Celery-задача отправки уведомлений из очереди."""

import asyncio
import logging

from app.config import get_settings
from app.db.base import async_session_factory
from app.db.models.user import User
from app.integrations.vk.client import VKClient
from app.repositories.notification_queue import NotificationQueueRepository
from app.tasks.celery_app import celery_app

logger = logging.getLogger("avacha.notifications")
settings = get_settings()


@celery_app.task(name="app.tasks.notifications.send_pending")
def send_pending(limit: int = 100) -> dict:
    """Разобрать очередь pending-уведомлений."""
    return asyncio.run(_send_pending(limit))


async def _send_pending(limit: int) -> dict:
    vk = VKClient()
    sent = failed = skipped = 0

    async with async_session_factory() as session:
        queue = NotificationQueueRepository(session)
        pending = await queue.get_pending(limit=limit)

        for notification in pending:
            sent_hour = await queue.count_sent_last_hour(notification.user_id)
            sent_day = await queue.count_sent_last_day(notification.user_id)

            if sent_hour >= settings.NOTIFICATION_RATE_LIMIT_PER_HOUR:
                await queue.mark_skipped(notification, "limit_per_hour")
                skipped += 1
                continue
            if sent_day >= settings.NOTIFICATION_RATE_LIMIT_PER_DAY:
                await queue.mark_skipped(notification, "limit_per_day")
                skipped += 1
                continue

            user = await session.get(User, notification.user_id)
            if user is None:
                await queue.mark_skipped(notification, "user_not_found")
                skipped += 1
                continue

            ok = await vk.send_notification(
                vk_user_id=user.vk_user_id,
                message=f"{notification.title}\n{notification.body}",
            )
            if ok:
                await queue.mark_sent(notification)
                sent += 1
            else:
                await queue.mark_failed(notification, "vk_send_failed")
                failed += 1

        await session.commit()

    logger.info(
        "notifications_processed",
        extra={"sent": sent, "failed": failed, "skipped": skipped},
    )
    return {"sent": sent, "failed": failed, "skipped": skipped}
