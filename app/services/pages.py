"""Сервис статичных страниц с кэшированием.

Страницы (О гонке, Правила, Организаторы) меняются редко —
кэшируем на час. Инвалидация происходит в админке при сохранении.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.static_page import StaticPageRepository
from app.schemas.page import PageDetail, PageListItem
from app.services.cache import cache

KEY_PAGE = "public:pages:page:{slug}"
KEY_LIST = "public:pages:list"


class PageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = StaticPageRepository(session)
        self.settings = get_settings()

    async def get_published(self, slug: str) -> PageDetail | None:
        cache_key = KEY_PAGE.format(slug=slug)
        cached = await cache.get(cache_key)
        if cached is not None:
            return PageDetail.model_validate(cached)

        page = await self.repo.get_published_by_slug(slug)
        if page is None:
            return None

        detail = PageDetail.model_validate(page)
        await cache.set(
            cache_key,
            detail.model_dump(mode="json"),
            ttl=self.settings.CACHE_TTL_PAGES,
        )
        return detail

    async def list_published(self) -> list[PageListItem]:
        cached = await cache.get(KEY_LIST)
        if cached is not None:
            return [PageListItem.model_validate(item) for item in cached]

        pages = await self.repo.list_published()
        items = [PageListItem.model_validate(p) for p in pages]
        await cache.set(
            KEY_LIST,
            [item.model_dump(mode="json") for item in items],
            ttl=self.settings.CACHE_TTL_PAGES,
        )
        return items
