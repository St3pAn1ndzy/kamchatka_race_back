from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.discipline import Discipline
    from app.db.models.stage import Stage


class Season(Base):
    """Сезон гонки нужен для просмотра прошлых лет и выбора сезон - этап"""

    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Берем в пример нашу гонку - она активная, а все остальные для мининарезок в эфире к примеру
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    disciplines: Mapped[list["Discipline"]] = relationship(
        back_populates="season",
        order_by="Discipline.sort_order",
    )

    stages: Mapped[list["Stage"]] = relationship(
        back_populates="season",
        order_by="Stage.order_index",
    )
