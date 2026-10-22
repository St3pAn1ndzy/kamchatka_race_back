from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import AwareDatetime

from app.api.deps import ScheduleEventRepoDep
from app.enums import ScheduleKind
from app.schemas.schedule import ScheduleEventListResponse, ScheduleEventResponse

router = APIRouter(
    prefix="/content/schedule",
    tags=["content"],
)

# Константы для защиты от переполнения Postgres
MAX_ID = 2147483647
MAX_OFFSET = 100_000


@router.get("", response_model=ScheduleEventListResponse)
async def list_schedule_events(
    schedule_events: ScheduleEventRepoDep,
    kind: Annotated[ScheduleKind | None, Query()] = None,
    stage_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
    starts_from: Annotated[AwareDatetime, Query()] | None = None,
    starts_to: Annotated[AwareDatetime, Query()] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> ScheduleEventListResponse:
    """Получить опубликованные события программы с фильтрами и пагинацией."""
    if starts_from is not None and starts_to is not None and starts_from > starts_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="starts_from не может быть позже starts_to",
        )

    items = await schedule_events.list_public(
        kind=kind,
        stage_id=stage_id,
        starts_from=starts_from,
        starts_to=starts_to,
        limit=limit,
        offset=offset,
    )

    total = await schedule_events.count_public(
        kind=kind,
        stage_id=stage_id,
        starts_from=starts_from,
        starts_to=starts_to,
    )

    return ScheduleEventListResponse(
        items=[ScheduleEventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{event_id}", response_model=ScheduleEventResponse)
async def get_schedule_event(
    event_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    schedule_events: ScheduleEventRepoDep,
) -> ScheduleEventResponse:
    """Получить одно опубликованное событие по идентификатору."""
    event = await schedule_events.get_public_by_id(event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Событие не найдено",
        )

    return ScheduleEventResponse.model_validate(event)
