from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.deps import FAQItemRepoDep
from app.schemas.content import FAQItemResponse, FAQListResponse

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/faq", response_model=FAQListResponse)
async def list_faq_items(
    faq_items: FAQItemRepoDep,
    category: Annotated[
        str | None,
        Query(min_length=1, max_length=100),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FAQListResponse:
    """Получить опубликованные вопросы с фильтром и пагинацией."""
    items = await faq_items.list_public(
        category=category,
        limit=limit,
        offset=offset,
    )
    total = await faq_items.count_public(category=category)

    return FAQListResponse(
        items=[FAQItemResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/faq/{faq_id}", response_model=FAQItemResponse)
async def get_faq_item(
    faq_id: Annotated[int, Path(gt=0)],
    faq_items: FAQItemRepoDep,
) -> FAQItemResponse:
    """Получить один опубликованный вопрос по идентификатору."""
    item = await faq_items.get_public_by_id(faq_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вопрос не найден",
        )
    return FAQItemResponse.model_validate(item)
