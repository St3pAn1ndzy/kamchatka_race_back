"""Зрительские локации: публичный список для карты."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, ViewerLocationRepoDep
from app.config import get_settings
from app.enums import ViewerLocationCategory, ViewerLocationKind
from app.schemas.content import ViewerLocationPublicResponse
from app.services.cache import cache

router = APIRouter(prefix="/content/viewer-locations", tags=["content"])

MAX_OFFSET = 10_000


@router.get(
    "",
    response_model=list[ViewerLocationPublicResponse],
    summary="Зрительские локации",
)
async def list_viewer_locations(
    session: SessionDep,
    viewer_locations: ViewerLocationRepoDep,
    kind: Annotated[ViewerLocationKind | None, Query(description="Тип локации")] = None,
    category: Annotated[
        ViewerLocationCategory | None,
        Query(description="Категория (food / kids / stages / areas / other)"),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Размер страницы, 1–100. По умолчанию 50.",
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
            le=MAX_OFFSET,
            description="Смещение от начала списка, 0–10000.",
        ),
    ] = 0,
) -> list[ViewerLocationPublicResponse]:
    """Публичные зрительские локации.

    Сортировка: по типу (start → finish → viewpoint → festival → other),
    затем по названию. Кэш 1 час.
    """
    cache_key = (
        f"public:viewer-locations:"
        f"{kind.value if kind else 'all'}:"
        f"{category.value if category else 'all'}:"
        f"{limit}:{offset}"
    )
    cached = await cache.get(cache_key)
    if cached is not None:
        return [ViewerLocationPublicResponse(**item) for item in cached]

    items = await viewer_locations.list_public(
        kind=kind, category=category, limit=limit, offset=offset
    )
    result = [ViewerLocationPublicResponse.model_validate(item) for item in items]

    settings = get_settings()
    await cache.set(
        cache_key,
        [r.model_dump(mode="json") for r in result],
        settings.CACHE_TTL_STAGES,
    )
    return result
