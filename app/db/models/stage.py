from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import StageStatus

# TODO: Раскомментировать когда появться модели (1)
# if TYPE_CHECKING:
#     from app.db.models.results import OfficialMark
#     from app.db.models.tracking import Device, TrackPoint


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    tracker_interval_seconds: Mapped[int] = mapped_column(Integer, default=1200)
    status: Mapped[str] = mapped_column(
        String(32),
        default=StageStatus.PLANNED.value,
        nullable=False,
        index=True,
    )

    # TODO: Раскомментировать когда появться модели (2)
    # checkpoints: Mapped[list["Checkpoint"]] = relationship(
    #     back_populates="stage", order_by="Checkpoint.order_index"
    # )
    # devices: Mapped[list["Device"]] = relationship(back_populates="stage")
    # track_points: Mapped[list["TrackPoint"]] = relationship(back_populates="stage")
    # official_marks: Mapped[list["OfficialMark"]] = relationship(back_populates="stage")
    # route_points: Mapped[list["RoutePoint"]] = relationship(
    #     back_populates="stage", order_by="RoutePoint.order_index",
    #     cascade="all, delete-orphan",
    # )
