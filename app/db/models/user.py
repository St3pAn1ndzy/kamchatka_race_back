from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    # TODO: раскомментировать, когда появится NotificationQueue (1)
    # from app.db.models.notifications import NotificationQueue
    from app.db.models.push_subscription import PushSubscription


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

    push_subscription: Mapped[Optional["PushSubscription"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # TODO: раскомментировать, когда появится NotificationQueue (2)
    # notifications: Mapped[list["NotificationQueue"]] = relationship(back_populates="user")
