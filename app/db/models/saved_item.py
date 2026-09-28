from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.faq_item import FAQItem
    from app.db.models.news_post import NewsPost
    from app.db.models.schedule_event import ScheduleEvent
    from app.db.models.user import User
    from app.db.models.viewer_location import ViewerLocation


class SavedItem(Base):
    """Закладка пользователя на один существующий материал приложения.

    Подписки на участников уже хранятся в FanSubscription.
    Здесь только ссылки на новости, FAQ, события или места.
    """

    __tablename__ = "saved_items"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(news_post_id, faq_item_id, schedule_event_id, viewer_location_id) = 1",
            name="ck_saved_items_one_material",
        ),
        # Нельзя дважды сохранить один объект одним пользователем.
        UniqueConstraint("user_id", "news_post_id", name="uq_saved_items_user_news"),
        UniqueConstraint("user_id", "faq_item_id", name="uq_saved_items_user_faq"),
        UniqueConstraint("user_id", "schedule_event_id", name="uq_saved_items_user_event"),
        UniqueConstraint("user_id", "viewer_location_id", name="uq_saved_items_user_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Закладки удалённого пользователя больше не нужны.
    # Отдельный index=True не нужен, так как user_id первый в составных UNIQUE выше.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Если сам материал удалён, удаляем закладку на него, не остальные материалы.
    # Все ссылки nullable по отдельности.
    news_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_posts.id", ondelete="CASCADE"), nullable=True
    )
    faq_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("faq_items.id", ondelete="CASCADE"), nullable=True
    )
    schedule_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_events.id", ondelete="CASCADE"), nullable=True
    )
    viewer_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("viewer_locations.id", ondelete="CASCADE"), nullable=True
    )

    # Время добавления в сохранённое; сортировку created_at DESC, id DESC
    # зададим в запросе профиля, когда появится API.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="saved_items")

    # Односторонних связей достаточно для открытия материала из закладки.
    news_post: Mapped[Optional["NewsPost"]] = relationship()
    faq_item: Mapped[Optional["FAQItem"]] = relationship()
    schedule_event: Mapped[Optional["ScheduleEvent"]] = relationship()

    viewer_location: Mapped[Optional["ViewerLocation"]] = relationship()
