from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import ParticipantStatus

if TYPE_CHECKING:
    from app.db.models.device import Device
    from app.db.models.discipline import Discipline
    from app.db.models.fun_subscription import FanSubscription
    from app.db.models.official_mark import OfficialMark
    from app.db.models.track_point import TrackPoint


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Каждый игрок имеет какую-либо дисциплину в гонке
    discipline_id: Mapped[int | None] = mapped_column(
        ForeignKey("disciplines.id", ondelete="SET NULL", name="participants_discipline_id_fkey"),
        nullable=True,
        index=True,
    )
    photo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    dogs_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ParticipantStatus.REGISTERED.value,
        nullable=False,
        index=True,
    )

    devices: Mapped[list["Device"]] = relationship(
        back_populates="participant",
    )

    track_points: Mapped[list["TrackPoint"]] = relationship(
        back_populates="participant",
        order_by="TrackPoint.recorded_at",
    )

    official_marks: Mapped[list["OfficialMark"]] = relationship(
        back_populates="participant",
    )

    fans: Mapped[list["FanSubscription"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
    )

    discipline_ref: Mapped[Optional["Discipline"]] = relationship(back_populates="participants")

    def __str__(self) -> str:
        return f"№{self.number} {self.name}"

    def __repr__(self) -> str:
        return f"<Participant id={self.id} number={self.number} name={self.name!r}>"
