from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import UserFeedbackKind, UserFeedbackStatus

if TYPE_CHECKING:
    from app.db.models.user import User


class UserFeedback(Base):
    """Обратная связь от пользователя приложения"""

    __tablename__ = "user_feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Feedback может прийти и от гостя, поэтому пользователь необязателен
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(32),
        default=UserFeedbackKind.OTHER.value,
        server_default=UserFeedbackKind.OTHER.value,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default=UserFeedbackStatus.NEW.value,
        server_default=UserFeedbackStatus.NEW.value,
        nullable=False,
        index=True,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Внутренняя заметка админа, не для публичного API
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    user: Mapped[Optional["User"]] = relationship(back_populates="feedback_items")
