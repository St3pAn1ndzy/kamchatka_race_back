from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.fun_subscription import FanSubscription
    from app.db.models.notification import NotificationQueue
    from app.db.models.push_subscription import PushSubscription
    from app.db.models.saved_item import SavedItem
    from app.db.models.share_event import ShareEvent
    from app.db.models.user_feedback import UserFeedback


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_user_id: Mapped[int] = mapped_column(unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[str] = mapped_column(String(255), default="")
    photo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notifications_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # --- 152-ФЗ: согласие на обработку ПДн ---
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Профиль / онбординг ---
    is_favorite_app: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    onboarding_passed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    push_subscription: Mapped[Optional["PushSubscription"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    notifications: Mapped[list["NotificationQueue"]] = relationship(back_populates="user")
    favorites: Mapped[list["FanSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Закладки на материалы, отдельно от подписки «Болею за».
    saved_items: Mapped[list["SavedItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    feedback_items: Mapped[list["UserFeedback"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )

    share_events: Mapped[list["ShareEvent"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or f"VK#{self.vk_user_id}"

    def __repr__(self) -> str:
        return f"<User id={self.id} vk_user_id={self.vk_user_id}>"
