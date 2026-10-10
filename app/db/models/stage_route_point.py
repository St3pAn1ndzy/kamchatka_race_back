from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stage import Stage


class StageRoutePoint(Base):
    __tablename__ = "stage_route_points"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_stage_route_points_position"),
        CheckConstraint("lat BETWEEN -90 AND 90", name="ck_stage_route_points_lat"),
        CheckConstraint("lon BETWEEN -180 AND 180", name="ck_stage_route_points_lon"),
        UniqueConstraint("stage_id", "position", name="uq_stage_route_points_stage_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    stage: Mapped["Stage"] = relationship(back_populates="route_points")
