from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.participant import Participant
    from app.db.models.user import User


class FanSubscription(Base):
    """Подписка «Болею за» — пользователь болеет за участника.

    Один пользователь — один голос за участника (уникальный индекс).
    Счётчик используется в рейтинге народной поддержки.
    """

    __tablename__ = "fan_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "participant_id", name="uq_fan_user_participant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="favorites")
    participant: Mapped["Participant"] = relationship(back_populates="fans")

    def __str__(self) -> str:
        return f"Пользователь {self.user_id} → участник {self.participant_id}"

    def __repr__(self) -> str:
        return f"<FanSubscription id={self.id} user_id={self.user_id} participant_id={self.participant_id}>"
