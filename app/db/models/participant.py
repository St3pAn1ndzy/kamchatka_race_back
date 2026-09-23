from typing import TYPE_CHECKING, Optional
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import ParticipantStatus


if TYPE_CHECKING:
    from app.db.models.device import Device
    from app.db.models.track_point import TrackPoint

    # TODO: Раскомментировать по ходу создания моделей (1)
    # from app.db.models.engagement import FanSubscription
    # from app.db.models.results import OfficialMark



class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[Optional[int]] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    discipline: Mapped[str] = mapped_column(String(100), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dogs_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ParticipantStatus.REGISTERED.value,
        nullable=False,
        index=True,
    )

    devices: Mapped[list["Device"]] = relationship(back_populates="participant")

    track_points: Mapped[list["TrackPoint"]] = relationship(back_populates="participant",
                                                            order_by="TrackPoint.recorded_at")

    # TODO: Раскомментировать по ходу создания моделей (2)
    # official_marks: Mapped[list["OfficialMark"]] = relationship(back_populates="participant")
    # fans: Mapped[list["FanSubscription"]] = relationship(back_populates="participant")
