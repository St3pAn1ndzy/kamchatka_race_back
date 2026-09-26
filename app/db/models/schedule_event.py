from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import ScheduleKind

if TYPE_CHECKING:
    from app.db.models.stage import Stage


class ScheduleEvent(Base):
    """Событие программы: гонка, культурное мероприятие или другое событие"""

    __tablename__ = "schedule_events"
    __table_args__ = (
        # Проверяем что конец события был валидным
        CheckConstraint(
            "ends_at is NULL or ends_at >= starts_at", name="ck_schedule_events_time_valid"
        )
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Название для списка событий и карточки мероприятия
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Подробности можно добавить позже.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Тип события
    kind: Mapped[str] = mapped_column(
        String(32), default=ScheduleKind.OTHER.value, nullable=False, index=True
    )

    # Событие может существовать без этапа, поэтому удаление этапа сохраняет событие.
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Начало события указывают явно, чтобы было заранее расписано все мероприятие
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # NULL означает, что время окончания пока не задано
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Название площадки или адрес, если они уже известны
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Флаг на публикацию события
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Время создания назначает база данных.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    stage: Mapped[Optional["Stage"]] = relationship(back_populates="schedule_events")
