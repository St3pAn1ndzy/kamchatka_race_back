from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import RaceState

if TYPE_CHECKING:
    from app.db.models.stage import Stage


class RaceStatus(Base):
    __tablename__ = "race_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(
        String(32),
        server_default=RaceState.UPCOMING.value,
        nullable=False,
        index=True,
    )
    current_stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    current_stage: Mapped[Optional["Stage"]] = relationship(foreign_keys=[current_stage_id])
