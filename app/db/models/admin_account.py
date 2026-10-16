from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.admin_session import AdminSession
    from app.db.models.audit_log import AuditLog
    from app.db.models.official_mark import OfficialMark


class AdminAccount(Base):
    """Учётная запись администратора.

    Может быть создана двумя способами:
    - через VK ID (vk_user_id), если админ заходит через VK;
    - через логин/пароль (login, password_hash).

    Пароль хранится в виде хеша (bcrypt). Никогда не в открытом виде.
    """

    __tablename__ = "admin_accounts"
    __table_args__ = (
        CheckConstraint(
            "login IS NOT NULL OR vk_user_id IS NOT NULL",
            name="ck_admin_accounts_has_identifier",
        ),
        CheckConstraint(
            "login IS NULL OR password_hash IS NOT NULL",
            name="ck_admin_accounts_password_required",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # VK ID для входа через VK. NULL, если админ входит по логину.
    vk_user_id: Mapped[int | None] = mapped_column(
        unique=True,
        nullable=True,
    )

    # Логин для входа по паролю. NULL, если админ входит через VK.
    login: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
    )

    # Хеш пароля (bcrypt). NULL для VK-админов.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Отображаемое имя админа
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    sessions: Mapped[list["AdminSession"]] = relationship(back_populates="admin")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="admin")
    entered_marks: Mapped[list["OfficialMark"]] = relationship(
        back_populates="entered_by",
    )

    def __str__(self) -> str:
        return self.login or self.display_name

    def __repr__(self) -> str:
        return f"<AdminAccount id={self.id} login={self.login!r}>"
