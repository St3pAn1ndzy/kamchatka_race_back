from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import NewsSource

if TYPE_CHECKING:
    from app.db.models.stage import Stage


class NewsPost(Base):
    """Новость гонки.

    Может быть создана вручную или импортирована из сообщества ВКонтакте.
    Публикация отделена от создания: черновик не виден в приложении.
    """

    __tablename__ = "news_posts"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Краткое описание для ленты. Если NULL — фронт обрежет body.
    lead: Mapped[str | None] = mapped_column(String(500), nullable=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)

    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Источник: manual | vk.
    source: Mapped[str] = mapped_column(
        String(32),
        default=NewsSource.MANUAL.value,
        nullable=False,
        index=True,
    )

    # Ссылка на пост ВК (для source=vk).
    vk_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Новость может быть привязана к этапу (например, «Итоги этапа 1»).
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Публикация. NULL — черновик.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Флаг публикации. Черновик не показывается в приложении.
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
        index=True,
    )

    # Важная новость — отправляется push-уведомлением.
    is_important: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )

    # Закреплённая новость — вверху ленты.
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    stage: Mapped[Optional["Stage"]] = relationship()
