from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.participant import Participant
    from app.db.models.stage import Stage
    from app.db.models.track_point import TrackPoint


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Порядковый номер устройства
    iridium_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Уникальный идентификатор устройства
    imei: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    # Его название
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Во время добавления устройства в базу данных, оно может быть не привязано к участнику и этапу, поэтому nullable=True
    participant_id: Mapped[int | None] = mapped_column(
        ForeignKey("participants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sos_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    participant: Mapped["Participant" | None] = relationship(back_populates="devices")
    stage: Mapped["Stage" | None] = relationship(back_populates="devices")

    track_points: Mapped[list["TrackPoint"]] = relationship(
        back_populates="device",
        order_by="TrackPoint.recorded_at",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
