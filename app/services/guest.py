"""Сервис раздела «Гостям» с кэшированием."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import GuestItemSection
from app.repositories.faq_item import FAQItemRepository
from app.repositories.guest import GuestItemRepository
from app.repositories.static_page import StaticPageRepository
from app.schemas.guest import (
    AccordionItem,
    AccordionPage,
    GuestItemResponse,
    GuestTabResponse,
    WhatToBringPage,
)
from app.services.cache import cache

KEY_WHAT_TO_BRING = "public:guests:what-to-bring"
KEY_GETTING_HERE = "public:guests:getting-here"
KEY_SAFETY = "public:guests:safety"

TAB_TITLES = {
    GuestItemSection.CLOTHING.value: "Одежда",
    GuestItemSection.SHOES.value: "Обувь",
    GuestItemSection.EQUIPMENT.value: "Снаряжение",
}

GETTING_HERE_CATEGORY = "getting_here"
SAFETY_CATEGORY = "safety"


class GuestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.item_repo = GuestItemRepository(session)
        self.page_repo = StaticPageRepository(session)
        self.faq_repo = FAQItemRepository(session)

    async def get_what_to_bring(self) -> WhatToBringPage:
        cached = await cache.get(KEY_WHAT_TO_BRING)
        if cached is not None:
            return WhatToBringPage.model_validate(cached)

        page = await self.page_repo.get_published_by_slug("guests-what-to-bring")
        cover_url = page.cover_url if page else None

        tabs: list[GuestTabResponse] = []
        for section in GuestItemSection:
            items = await self.item_repo.list_by_section(section.value)
            if not items:
                continue
            tabs.append(
                GuestTabResponse(
                    code=section.value,
                    title=TAB_TITLES[section.value],
                    items=[GuestItemResponse.model_validate(it) for it in items],
                )
            )

        result = WhatToBringPage(cover_url=cover_url, tabs=tabs)
        await cache.set(
            KEY_WHAT_TO_BRING, result.model_dump(mode="json"), ttl=self.settings.CACHE_TTL_PAGES
        )
        return result

    async def get_getting_here(self) -> AccordionPage:
        cached = await cache.get(KEY_GETTING_HERE)
        if cached is not None:
            return AccordionPage.model_validate(cached)

        page = await self.page_repo.get_published_by_slug("guests-getting-here")
        cover_url = page.cover_url if page else None
        faq_items = await self.faq_repo.list_all_by_category(GETTING_HERE_CATEGORY)

        result = AccordionPage(
            title="Как добраться",
            cover_url=cover_url,
            items=[AccordionItem(title=it.question, content=it.answer) for it in faq_items],
        )
        await cache.set(
            KEY_GETTING_HERE, result.model_dump(mode="json"), ttl=self.settings.CACHE_TTL_PAGES
        )
        return result

    async def get_safety(self) -> AccordionPage:
        cached = await cache.get(KEY_SAFETY)
        if cached is not None:
            return AccordionPage.model_validate(cached)

        page = await self.page_repo.get_published_by_slug("guests-safety")
        cover_url = page.cover_url if page else None
        faq_items = await self.faq_repo.list_all_by_category(SAFETY_CATEGORY)

        result = AccordionPage(
            title="Безопасность зимой",
            cover_url=cover_url,
            items=[AccordionItem(title=it.question, content=it.answer) for it in faq_items],
        )
        await cache.set(
            KEY_SAFETY, result.model_dump(mode="json"), ttl=self.settings.CACHE_TTL_PAGES
        )
        return result
