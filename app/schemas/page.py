"""Pydantic-схемы для статичных страниц."""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.base import BaseSchema


class PageListItem(BaseSchema):
    """Короткая карточка страницы — для меню «Ещё»."""

    slug: str = Field(..., description="Уникальный ключ: about / rules / organizers")
    title: str = Field(..., description="Заголовок для меню")


class PageDetail(BaseSchema):
    """Полная страница — для отображения контента."""

    slug: str
    title: str
    content: str = Field(..., description="Markdown/HTML с картинками")
    cover_url: str | None = Field(None, description="URL обложки (1200×675)")
    updated_at: datetime | None = None
