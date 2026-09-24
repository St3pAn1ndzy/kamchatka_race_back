from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FAQItem(Base):
    """Вопрос-ответ для справочного раздела приложения"""

    __tablename__ = "faq_items"
    __table_args__ = (
        # Ограничение на то, что порядковый номер вопроса не может быть отрицательным
        CheckConstraint("order_index >= 0", name="ck_faq_items_order_index_nonnegative"),
        Index("ix_faq_items_question_answer", "question", "answer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Короткий заголовок вопроса, который будет отображаться в списке вопросов (предлагаю ограничить 500 символами)
    question: Mapped[str] = mapped_column(String(500), nullable=False)

    # Полный текст ответа на вопрос (может быть длинным, поэтому Text)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # Порядковый номер вопроса в списке (по умолчания первый)
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    # Новая запись как черновик, сама же публикация будет проходить явно
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    # Дата и время создания записи (по умолчания время назначает БД)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
