from datetime import datetime

from app.schemas.base import BaseSchema


class ScheduleEventResponse(BaseSchema):
    """Опубликованное событие программы для публичного API."""

    id: int
    title: str
    description: str | None = None
    kind: str
    stage_id: int | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = None
    updated_at: datetime


class ScheduleEventListResponse(BaseSchema):
    """Страница событий программы с данными пагинации."""

    items: list[ScheduleEventResponse]
    total: int
    limit: int
    offset: int
