"""Публичный API для экрана карты и трекинга этапов."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, HTTPException, status
from pydantic import AwareDatetime

from app.api.deps import SessionDep
from app.schemas.public_stages import (
    CheckpointPublicResponse,
    LeadersResponse,
    PositionPublicResponse,
    StageTrackResponse,
)
from app.services.public_map import PublicMapService

router = APIRouter(prefix="/stages", tags=["stages"])

# Константа для максимального ID (INTEGER в Postgres)
MAX_ID = 2147483647


@router.get(
    "/{stage_id}/track",
    response_model=StageTrackResponse,
    responses={
        404: {"description": "Этап не найден или маршрут не загружен"},
    },
)
async def get_stage_track(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
) -> StageTrackResponse:
    """GeoJSON нитка маршрута этапа."""
    track = await PublicMapService(session).get_stage_route_geojson(stage_id)

    if track is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Маршрут этапа не найден",
        )

    return track


@router.get("/{stage_id}/checkpoints", response_model=list[CheckpointPublicResponse])
async def get_stage_checkpoints(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
) -> list[CheckpointPublicResponse]:
    """Список КП этапа (с высотами и километражом)."""
    return await PublicMapService(session).get_checkpoints(stage_id)


@router.get("/{stage_id}/positions", response_model=list[PositionPublicResponse])
async def get_stage_positions(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    since: Annotated[AwareDatetime, Query()] | None = None,
) -> list[PositionPublicResponse]:
    """Последние координаты всех участников на этапе."""
    return await PublicMapService(session).get_positions(stage_id, since=since)


@router.get("/{stage_id}/leaders", response_model=LeadersResponse)
async def get_stage_leaders(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    discipline: str | None = Query(default=None, description="Код дисциплины"),
    as_of: Annotated[AwareDatetime, Query()] | None = None,
) -> LeadersResponse:
    """Рейтинг участников по судейским отметкам."""
    return await PublicMapService(session).get_leaders(stage_id, discipline=discipline, as_of=as_of)
