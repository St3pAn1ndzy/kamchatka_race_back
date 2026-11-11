from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import NotificationStatus

if TYPE_CHECKING:
    from app.db.models.user import User


class NotificationQueue(Base):
    """Очередь push-уведомлений.

    VK даёт лимит (2/час, 10/сутки на пользователя). Поэтому уведомления
    не отправляются сразу — ставятся в очередь и разбираются Celery-задачей
    с учётом лимитов.

    Формулировки содержат время данных («данные на 14:32»), не «прямо сейчас».
    """

    __tablename__ = "notification_queue"

    __table_args__ = (Index("ix_notification_queue_status_scheduled", "status", "scheduled_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип события
    # Значения — из NotificationEventType (app/enums.py).
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус
    # Значения — из NotificationStatus (app/enums.py).
    status: Mapped[str] = mapped_column(
        String(32),
        default=NotificationStatus.PENDING.value,
        nullable=False,
    )

    # Сколько раз пытались отправить. При превышении лимита — skipped.
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    # Когда отправлять (для отложенных уведомлений).
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Когда фактически отправлено. NULL — ещё не отправлено.
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Текст ошибки, если отправка упала.
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="notifications")

    def __str__(self) -> str:
        return f"[{self.status}] {self.title[:80]}"

    def __repr__(self) -> str:
        return f"<NotificationQueue id={self.id} status={self.status!r}>"
