from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.schemas.map import MapCheckpointsResponse, MapParticipantsResponse, MapTrackResponse
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
    responses={404: {"description": "Этап не найден"}},
)
async def map_participants(
    session: SessionDep,
    stage_id: StageId,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> MapParticipantsResponse:
    return await PublicMapService(session).get_participants(stage_id, limit=limit, offset=offset)


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


@router.get(
    "/checkpoints",
    response_model=MapCheckpointsResponse,
    responses={404: {"description": "Этап не найден"}},
)
async def map_checkpoints(session: SessionDep, stage_id: StageId) -> MapCheckpointsResponse:
    return await PublicMapService(session).get_checkpoints(stage_id)
