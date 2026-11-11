"""Схемы публичного API справочников гонки."""

from datetime import datetime

from app.enums import StageStatus
from app.schemas.base import BaseSchema


class SeasonPublicResponse(BaseSchema):
    """Активный сезон — минимум для шапки приложения."""

    id: int
    year: int
    title: str
    starts_at: datetime | None
    ends_at: datetime | None


class DisciplinePublicResponse(BaseSchema):
    """Дисциплина для фильтра на экранах «Карта» и «Участники»."""

    id: int
    code: str
    name: str
    sort_order: int


class StagePublicResponse(BaseSchema):
    """Этап для переключателя на карте и раздела «Маршрут»."""

    id: int
    number: int
    name: str
    distance_km: float
    start_time: datetime | None
    finish_time: datetime | None
    order_index: int
    status: StageStatus
