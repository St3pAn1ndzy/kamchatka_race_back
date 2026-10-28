from datetime import datetime

from app.enums import ViewerLocationCategory, ViewerLocationKind
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


class ViewerLocationPublicResponse(BaseSchema):
    """Публичная зрительская локация для карты."""

    id: int
    name: str
    kind: ViewerLocationKind
    category: ViewerLocationCategory
    lat: float
    lon: float
    address: str | None = None
    description: str | None = None
    directions: str | None = None
    travel_time_minutes: int | None = None
    parking_info: str | None = None
    facilities: list[str] | None = None
    photo_url: str | None = None
    first_arrival_planned_at: datetime | None = None
    safety_notes: str | None = None
