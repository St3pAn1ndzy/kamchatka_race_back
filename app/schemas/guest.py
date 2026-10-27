"""Схемы раздела «Гостям»."""

from pydantic import BaseModel, ConfigDict, Field


class GuestItemResponse(BaseModel):
    """Один блок внутри таба (например, «Первый слой» одежды)."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    text: str
    image_url: str | None = None


class GuestTabResponse(BaseModel):
    """Таб (Одежда / Обувь / Снаряжение)."""

    code: str
    title: str
    items: list[GuestItemResponse]


class WhatToBringPage(BaseModel):
    """Страница «Что взять с собой»."""

    title: str = "Что взять с собой"
    cover_url: str | None = None
    tabs: list[GuestTabResponse]


class AccordionItem(BaseModel):
    """Один элемент аккордеона (вопрос-ответ)."""

    title: str
    content: str


class AccordionPage(BaseModel):
    """Универсальная страница с аккордеоном (Как добраться / Безопасность)."""

    title: str
    cover_url: str | None = None
    items: list[AccordionItem]
