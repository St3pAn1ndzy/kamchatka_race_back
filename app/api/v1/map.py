from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.deps import SessionDep
from app.schemas.map import MapParticipantsResponse, MapTrackResponse
from app.services.public_directory import PublicDirectoryService
from app.services.public_map import PublicMapService

router = APIRouter(prefix="/map", tags=["map"])

# Защита от переполнения Postgres
MAX_ID = 2147483647
MAX_OFFSET = 100_000

# алиас для stage_id
StageId = Annotated[int, Query(gt=0, le=MAX_ID)]


@router.get(
    "/participants",
    response_model=MapParticipantsResponse,
    responses={404: {"description": "Активный сезон или этап не найден"}},
)
async def map_participants(
    session: SessionDep,
    stage_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
    discipline_ids: Annotated[
        list[int] | None,
        Query(gt=0, le=MAX_ID, description="Фильтр по дисциплинам"),
    ] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> MapParticipantsResponse:
    """Участники на карте.

    Если stage_id не передан — используется активный этап сезона.
    """
    if stage_id is None:
        directory = PublicDirectoryService(session)
        active = await directory.get_active_stage()
        if active is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Активный этап не найден")
        stage_id = active.id

    return await PublicMapService(session).get_participants(
        stage_id,
        discipline_ids=discipline_ids,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/entry/{entry_id}/track",
    response_model=MapTrackResponse,
    responses={404: {"description": "Этап или участник не найден"}},
)
async def map_entry_track(
    entry_id: Annotated[int, Path(gt=0, le=MAX_ID, description="Participant ID")],
    session: SessionDep,
    stage_id: StageId,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> MapTrackResponse:
    return await PublicMapService(session).get_track(stage_id, entry_id, limit=limit, offset=offset)
