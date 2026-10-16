from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.admin_account import AdminAccount


class AuditLog(Base):
    """Журнал действий администраторов.

    Каждое изменение через админку пишет запись сюда: кто, что, когда.
    Это требование безопасности и разбора инцидентов.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # SET NULL: если админа удалят, запись журнала остаётся.
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Действие
    action: Mapped[str] = mapped_column(String(64), nullable=False)

    # Тип сущности над который производили действие
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # ID сущности над который производили действие
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Дополнительные данные: что было до и после.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    admin: Mapped[Optional["AdminAccount"]] = relationship(back_populates="audit_logs")

    def __str__(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action} created_at={self.created_at!r}>"
