from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.participant import Participant
    from app.db.models.stage import Stage

    # TODO: Раскомментировать, когда появится модель TrackPoint
    # from app.db.models.tracking.track_point import TrackPoint


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)

    iridium_number: Mapped[str] = mapped_column(String(100),
                                                unique=True,
                                                nullable=False,
                                                index=True)

    imei: Mapped[str] = mapped_column(String(32),
                                      unique=True,
                                      nullable=False,
                                      index=True)

    name: Mapped[str] = mapped_column(String(255),
                                      nullable=False)

    participant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("participants.id", ondelete="SET NULL"),
                                                          nullable=True,
                                                          index=True)

    stage_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stages.id", ondelete="SET NULL"),
                                                nullable=True,
                                                index=True)

    is_active: Mapped[bool] = mapped_column(Boolean,
                                            default=True,
                                            nullable=False)

    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True),
                                                                nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 onupdate=func.now(),
                                                 nullable=False)

    participant: Mapped[Optional["Participant"]] = relationship(back_populates="devices")
    stage: Mapped[Optional["Stage"]] = relationship(back_populates="devices")

    # TODO: Раскомментировать, когда появится модель TrackPoint (2)
    # track_points: Mapped[list["TrackPoint"]] = relationship(back_populates="device",
    #     order_by="TrackPoint.measured_at",
    #     cascade="all, delete-orphan")

