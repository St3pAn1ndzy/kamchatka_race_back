from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import AwareDatetime

from app.api.deps import NewsPostRepoDep
from app.enums import NewsSource
from app.schemas.news import (
    NewsPostListItemResponse,
    NewsPostListResponse,
    NewsPostResponse,
)

router = APIRouter(prefix="/content/news", tags=["content"])

MAX_ID = 2147483647
MAX_OFFSET = 100_000


@router.get("", response_model=NewsPostListResponse)
async def list_news_posts(
    news_posts: NewsPostRepoDep,
    source: Annotated[NewsSource | None, Query()] = None,
    stage_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
    important_only: Annotated[bool, Query()] = False,
    published_from: Annotated[AwareDatetime, Query()] | None = None,
    published_to: Annotated[AwareDatetime, Query()] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> NewsPostListResponse:
    """Получить опубликованные новости с фильтрами и пагинацией."""
    if published_from is not None and published_to is not None and published_from > published_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="published_from не может быть позже published_to",
        )

    now = datetime.now(tz=UTC)
    items = await news_posts.list_public(
        source=source,
        stage_id=stage_id,
        important_only=important_only,
        published_from=published_from,
        published_to=published_to,
        now=now,
        limit=limit,
        offset=offset,
    )
    total = await news_posts.count_public(
        source=source,
        stage_id=stage_id,
        important_only=important_only,
        published_from=published_from,
        published_to=published_to,
        now=now,
    )

    return NewsPostListResponse(
        items=[NewsPostListItemResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{news_id}",
    response_model=NewsPostResponse,
    responses={404: {"description": "Новость не найдена"}},
)
async def get_news_post(
    news_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    news_posts: NewsPostRepoDep,
) -> NewsPostResponse:
    """Получить полное содержимое одной опубликованной новости."""
    now = datetime.now(tz=UTC)
    news_post = await news_posts.get_public_by_id(news_id, now=now)
    if news_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Новость не найдена",
        )
    return NewsPostResponse.model_validate(news_post)
