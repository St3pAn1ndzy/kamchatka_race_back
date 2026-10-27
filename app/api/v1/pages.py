"""Роутер публичных статичных страниц (О гонке, Правила, Организаторы)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.api.deps import SessionDep
from app.schemas.page import PageDetail, PageListItem
from app.services.pages import PageService

router = APIRouter(prefix="/pages", tags=["pages"])

MAX_SLUG_LENGTH = 50


@router.get(
    "/",
    response_model=list[PageListItem],
    summary="Список опубликованных страниц",
    description="Используется для меню «Ещё» в VK Mini App.",
)
async def list_pages(session: SessionDep) -> list[PageListItem]:
    service = PageService(session)
    return await service.list_published()


@router.get(
    "/{slug}",
    response_model=PageDetail,
    responses={404: {"description": "Страница не найдена"}},
    summary="Получить страницу по slug",
)
async def get_page(
    slug: Annotated[
        str,
        Path(
            min_length=1,
            max_length=MAX_SLUG_LENGTH,
            description="Ключ страницы: about / rules / organizers",
        ),
    ],
    session: SessionDep,
) -> PageDetail:
    service = PageService(session)
    page = await service.get_published(slug)
    if page is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Страница не найдена",
        )
    return page
