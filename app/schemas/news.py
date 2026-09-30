from datetime import datetime

from app.enums import NewsSource
from app.schemas.base import BaseSchema


class NewsPostListItemResponse(BaseSchema):
    """Короткая карточка новости для ленты."""

    id: int
    title: str
    lead: str | None = None
    cover_url: str | None = None
    source: NewsSource
    stage_id: int | None = None
    published_at: datetime
    is_important: bool
    is_pinned: bool


class NewsPostResponse(NewsPostListItemResponse):
    """Полная опубликованная новость."""

    body: str
    vk_url: str | None = None
    updated_at: datetime


class NewsPostListResponse(BaseSchema):
    """Страница новостей с метаданными offset-пагинации."""

    items: list[NewsPostListItemResponse]
    total: int
    limit: int
    offset: int
