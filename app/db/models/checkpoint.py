from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums import CheckpointKind

if TYPE_CHECKING:
    from app.db.models.official_mark import OfficialMark
    from app.db.models.stage import Stage


class Checkpoint(Base):
    """Контрольный пункт (КП) на этапе.

    Может быть стартом, финишем или промежуточным КП.
    Официальное время прохождения фиксируется судьёй (OfficialMark).
    """

    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)

    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Короткий код для отображения и уведомлений: «КП-1», «Старт», «Финиш».
    code: Mapped[str] = mapped_column(String(32), nullable=False)

    # Полное название: «Контрольный пункт у ручья».
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Тип: start | finish | checkpoint
    kind: Mapped[str] = mapped_column(
        String(32),
        default=CheckpointKind.CHECKPOINT.value,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Километр от старта гонки (не этапа). Для легенды и профиля высот.
    km_from_race_start: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Порядок прохождения на этапе.
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Есть ли на КП судья (кто фиксирует официальное время).
    has_judge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Флаг публикации: черновик не показывается в приложении.
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stage: Mapped["Stage"] = relationship(back_populates="checkpoints")

    official_marks: Mapped[list["OfficialMark"]] = relationship(
        back_populates="checkpoint",
    )

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"
