from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FAQItem(Base):
    """Вопрос-ответ для справочного раздела приложения"""

    __tablename__ = "faq_items"
    __table_args__ = (
        # Ограничение на то, что порядковый номер вопроса не может быть отрицательным
        CheckConstraint("order_index >= 0", name="ck_faq_items_order_index_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Короткий заголовок вопроса, который будет отображаться в списке вопросов (предлагаю ограничить 500 символами)
    question: Mapped[str] = mapped_column(String(500), nullable=False)

    # Полный текст ответа на вопрос (может быть длинным, поэтому Text)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # Категория вопроса, NULL означает, что категория не выбрана
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Порядковый номер вопроса в списке
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # Новая запись как черновик, сама же публикация будет проходить явно
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    # Дата и время создания записи (по умолчания время назначает БД)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # При создании заполняется текущим временем.
    # При UPDATE через SQLAlchemy обновляется автоматически, если updated_at не передан явно
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __str__(self) -> str:
        return self.question[:80]

    def __repr__(self) -> str:
        return f"<FAQItem id={self.id} question={self.question[:50]!r}>"
