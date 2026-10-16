from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.admin_account import AdminAccount


class AdminSession(Base):
    """Серверная сессия администратора.

    Хранится в БД, чтобы можно было отозвать мгновенно (увольнение,
    потерянный ноутбук). JWT админа содержит session_id; при каждом
    запросе проверяется, что сессия жива.
    """

    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Время жизни сессии
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Время отзыва. NULL — сессия активна.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    admin: Mapped["AdminAccount"] = relationship(back_populates="sessions")

    def __str__(self) -> str:
        return self.session_id

    def __repr__(self) -> str:
        return f"<AdminSession session_id={self.session_id} expires_at={self.expires_at!r}>"
