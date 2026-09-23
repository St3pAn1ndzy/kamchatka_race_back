from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.device import Device
    from app.db.models.participant import Participant
    from app.db.models.stage import Stage


class TrackPoint(Base):
    __tablename__ = "track_points"

    #Проверяем координаты на валидность, а также создаем индекс по device_id и recorded_at для ускорения выборки
    __table_args__ = (
        CheckConstraint("lat >= -90 AND lat <= 90", name="bad_track_points_lat"),
        CheckConstraint("lon >= -180 AND lon <= 180", name="bad_track_points_lon"),
        Index("index_track_points_device_recorded_at","device_id", "recorded_at")
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    iridium_point_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    deduplication_key: Mapped[str] = mapped_column(String(64),
                                                   unique=True,
                                                   nullable=False,
                                                   index=True)

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)

    participant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("participants.id", ondelete="SET NULL"),
                                                          nullable=True,
                                                          index=True)

    stage_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True, index=True)

    lat: Mapped[float] = mapped_column(Float, nullable=False)

    lon: Mapped[float] = mapped_column(Float, nullable=False)

    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    course_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    source_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    average_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    km_from_start: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    #Время получения точки gps и время записи точки gps на устройстве могут отличаться, поэтому я сделал два поля
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  nullable=False,
                                                  index=True)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False)

    #Флаг, который указывает, что точка была подтверждена (проверена админом или системой)
    #Подтвержденные точки могут быть использованы для расчета результатов,
    # а неподтвержденные точки могут быть удалены или проигнорированы
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False,
                                               server_default=false(),
                                               nullable=False,
                                               index=True)

    device: Mapped["Device"] = relationship(back_populates="track_points")

    participant: Mapped[Optional["Participant"]] = relationship(back_populates="track_points")

    stage: Mapped[Optional["Stage"]] = relationship(back_populates="track_points")


