from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.participant import Participant
    from app.db.models.season import Season


class Discipline(Base):
    """Дисциплина привязана к сезону, потому что набор зачётов может меняться каждый год"""

    __tablename__ = "disciplines"
    __table_args__ = (UniqueConstraint("season_id", "code", name="uq_disciplines_season_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE", name="disciplines_season_id_fkey"),
        nullable=False,
        index=True,
    )
    # Короткое название (по типу sani-8 и тд)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Соответственно уже полное название дисциплины (Нарта, ездовые собаки 8 - ...)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    season: Mapped["Season"] = relationship(back_populates="disciplines")
    participants: Mapped[list["Participant"]] = relationship(back_populates="discipline_ref")

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Discipline id={self.id} code={self.code!r}>"
