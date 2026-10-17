"""Сервис для отправки уведомлений из админ-панели."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fun_subscription import FanSubscription
from app.db.models.notification import NotificationQueue
from app.db.models.participant import Participant
from app.db.models.user import User
from app.enums import NotificationEventType, NotificationStatus


class AdminNotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_participants(self) -> list[Participant]:
        """Получить список участников для выпадающего списка."""
        stmt = select(Participant).order_by(Participant.number)
        return list((await self.session.execute(stmt)).scalars().all())

    async def send_broadcast(self, title: str, body: str, target_participant_id: int | None) -> int:
        """Создает задачи в очереди. Возвращает количество получателей."""

        # 1. Определяем аудиторию
        if target_participant_id:
            # Только те, кто подписан на конкретного участника
            stmt = (
                select(User.id)
                .join(FanSubscription, User.id == FanSubscription.user_id)
                .where(FanSubscription.participant_id == target_participant_id)
            )
        else:
            # Всем, у кого включены уведомления
            stmt = select(User.id).where(User.notifications_allowed.is_(True))

        user_ids = (await self.session.execute(stmt)).scalars().all()

        if not user_ids:
            return 0

        now = datetime.now(tz=UTC)

        # 2. Пачкой создаем записи в очереди
        for uid in user_ids:
            self.session.add(
                NotificationQueue(
                    user_id=uid,
                    event_type=NotificationEventType.BROADCAST.value,
                    title=title,
                    body=body,
                    status=NotificationStatus.PENDING.value,
                    scheduled_at=now,
                    attempts=0,
                )
            )

        await self.session.commit()
        return len(user_ids)
