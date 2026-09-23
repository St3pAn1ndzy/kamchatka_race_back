from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import StageStatus


if TYPE_CHECKING:
    from app.db.models.tracking.device import Device

    # TODO: Раскомментировать когда появятся модели (1)
    # from app.db.models.results import OfficialMark
    # from app.db.models.tracking import TrackPoint


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finish_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    tracker_interval_seconds: Mapped[int] = mapped_column(Integer, default=1200)
    status: Mapped[str] = mapped_column(
        String(32),
        default=StageStatus.PLANNED.value,
        nullable=False,
        index=True,
    )

    devices: Mapped[list["Device"]] = relationship(back_populates="stage")

    # TODO: Раскомментировать когда появяться модели (2)
    # checkpoints: Mapped[list["Checkpoint"]] = relationship(
    #     back_populates="stage", order_by="Checkpoint.order_index"
    # )
    # track_points: Mapped[list["TrackPoint"]] = relationship(back_populates="stage")
    # official_marks: Mapped[list["OfficialMark"]] = relationship(back_populates="stage")
    # route_points: Mapped[list["RoutePoint"]] = relationship(
    #     back_populates="stage", order_by="RoutePoint.order_index",
    #     cascade="all, delete-orphan",
    # )
