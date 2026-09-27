from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.admin_account import AdminAccount
    from app.db.models.checkpoint import Checkpoint
    from app.db.models.participant import Participant


class OfficialMark(Base):
    """Судейская отметка — единственный источник официального времени.

    Трекер не может перезаписать эту запись. При расхождении с трекером
    приоритет у судейской отметки (требование брифа).

    Исправление не удаляет запись: старая помечается is_cancelled=True,
    новая ссылается на старую через cancels_mark_id.
    """

    __tablename__ = "official_marks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # RESTRICT: нельзя удалить участника/КП, пока есть официальные отметки.
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    checkpoint_id: Mapped[int] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Официальное время прохождения КП. Ставит судья.
    mark_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    penalty_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    mandatory_stop_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # RESTRICT: нельзя удалить админа, пока есть его отметки.
    entered_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Отмена без физического удаления. История сохраняется.
    is_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
        index=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Если эта отметка заменяет другую — ссылка на заменённую.
    cancels_mark_id: Mapped[int | None] = mapped_column(
        ForeignKey("official_marks.id", ondelete="SET NULL"),
        nullable=True,
    )

    participant: Mapped["Participant"] = relationship(back_populates="official_marks")
    checkpoint: Mapped["Checkpoint"] = relationship(back_populates="official_marks")

    entered_by: Mapped["AdminAccount"] = relationship(
        foreign_keys=[entered_by_admin_id],
        back_populates="entered_marks",
    )

    # Self-referential: какая отметка была отменена этой.
    cancels_mark: Mapped[Optional["OfficialMark"]] = relationship(
        remote_side=[id],
        foreign_keys=[cancels_mark_id],
    )
