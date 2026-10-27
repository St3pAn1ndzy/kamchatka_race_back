"""Эндпоинты раздела «Гостям»."""

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.guest import AccordionPage, WhatToBringPage
from app.services.guest import GuestService

router = APIRouter(prefix="/guests", tags=["guests"])


@router.get(
    "/what-to-bring",
    response_model=WhatToBringPage,
    summary="Что взять с собой",
)
async def get_what_to_bring(session: SessionDep) -> WhatToBringPage:
    service = GuestService(session)
    return await service.get_what_to_bring()


@router.get(
    "/getting-here",
    response_model=AccordionPage,
    summary="Как добраться",
)
async def get_getting_here(session: SessionDep) -> AccordionPage:
    service = GuestService(session)
    return await service.get_getting_here()


@router.get(
    "/safety",
    response_model=AccordionPage,
    summary="Безопасность зимой",
)
async def get_safety(session: SessionDep) -> AccordionPage:
    service = GuestService(session)
    return await service.get_safety()
