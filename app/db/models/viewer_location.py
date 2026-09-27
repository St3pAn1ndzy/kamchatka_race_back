from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Stage


class ViewerLocation(Base):
    """Публичное место для зрителей: старт, финиш или площадка фестиваля

    Это справочник организаторов"""

    __tablename__ = "viewer_location"

    __table_args__ = (
        # Проверяем координаты на валидность, чтобы не было ошибок при внесении в БД
        CheckConstraint("lat >= -90 AND lat <= 90", name="ck_viewer_locations_lat_valid"),
        CheckConstraint("lon >= -180 AND lon <= 180", name="ck_viewer_locations_lon_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Название точки на карте и в списке мест
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    kind: Mapped[str] = mapped_column(String(32), nullable=False)

    # Координаты площадки, если например она между к/п гонки, без адреса
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    # Адрес площадки, чтобы зрители могли найти её на карте
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Как добраться: дорога, транспорт, парковка или пеший маршрут
    directions: Mapped[str | None] = mapped_column(Text, nullable=False)

    # Площадка может не относиться ни к одному из этапов, а быть просто местом для зрителей
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Новая площадка — черновик
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    stage: Mapped[Optional["Stage"]] = relationship(back_populates="viewer_locations")
