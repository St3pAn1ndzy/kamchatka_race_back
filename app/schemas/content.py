from datetime import datetime

from app.schemas.base import BaseSchema


class FAQItemResponse(BaseSchema):
    """Опубликованный вопрос - ответ для публичного API."""

    id: int
    question: str
    answer: str
    category: str | None = None
    order_index: int
    updated_at: datetime


class FAQListResponse(BaseSchema):
    """Страница опубликованных вопросов с данными пагинации."""

    items: list[FAQItemResponse]
    total: int
    limit: int
    offset: int
