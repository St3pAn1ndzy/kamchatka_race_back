from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Integer,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import ViewerLocationKind

if TYPE_CHECKING:
    from app.db.models.stage import Stage


class ViewerLocation(Base):
    """Публичное место для зрителей: старт, финиш или площадка фестиваля

    Это справочник организаторов"""

    __tablename__ = "viewer_locations"

    __table_args__ = (
        # Проверяем координаты на валидность, чтобы не было ошибок при внесении в БД
        CheckConstraint("lat >= -90 AND lat <= 90", name="ck_viewer_locations_lat_valid"),
        CheckConstraint("lon >= -180 AND lon <= 180", name="ck_viewer_locations_lon_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Название точки на карте и в списке мест
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    kind: Mapped[str] = mapped_column(
        String(32), default=ViewerLocationKind.VIEWPOINT.value, nullable=False
    )

    # Координаты площадки, если например она между к/п гонки, без адреса
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    # Адрес площадки, чтобы зрители могли найти её на карте
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Как добраться: дорога, транспорт, парковка или пеший маршрут
    directions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Сколько времени добираться до площадки
    travel_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Сведения о парковке: где, сколько мест, платная/бесплатная, есть ли охрана и тд
    parking_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Удобства площадки: парковка, кофе, туалет и тд
    facilities: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )

    photo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Планируемое время прибытия первых участников на площадку
    first_arrival_planned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Площадка может не относиться ни к одному из этапов, а быть просто местом для зрителей
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Техника безопасности
    safety_notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # Новая площадка — черновик
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    stage: Mapped[Optional["Stage"]] = relationship(back_populates="viewer_locations")
