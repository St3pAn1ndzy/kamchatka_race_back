from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import ShareEventChannel, ShareEventTargetKind

if TYPE_CHECKING:
    from app.db.models.user import User


class ShareEvent(Base):
    """Событие шаринга из приложения"""

    __tablename__ = "share_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Пользователь может быть неизвестен, если событие пришло от гостя
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Что именно пытались расшарить: участника, новость, чекпоинт или весь проект
    target_kind: Mapped[str] = mapped_column(
        String(32),
        default=ShareEventTargetKind.APP.value,
        server_default=ShareEventTargetKind.APP.value,
        nullable=False,
        index=True,
    )

    # ID сущности нужен только для конкретных материалов
    target_id: Mapped[int | None] = mapped_column(nullable=True, index=True)

    # Канал, через который пользователь делился материалом
    channel: Mapped[str] = mapped_column(
        String(32),
        default=ShareEventChannel.OTHER.value,
        server_default=ShareEventChannel.OTHER.value,
        nullable=False,
        index=True,
    )
    # Экран или место в приложении, откуда нажали кнопку поделиться
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Дополнительные данные оставляем гибкими для аналитики
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="share_events")

    def __str__(self) -> str:
        return f"Шаринг {self.target_kind}#{self.target_id} ({self.channel})"

    def __repr__(self) -> str:
        return (
            f"<ShareEvent id={self.id} target_kind={self.target_kind!r} target_id={self.target_id}>"
        )
