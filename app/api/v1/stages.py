"""Публичный API для экрана карты и трекинга этапов."""

from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import AwareDatetime

from app.api.deps import SessionDep
from app.services.public_map import PublicMapService

router = APIRouter(prefix="/stages", tags=["stages"])

# Константа для максимального ID (INTEGER в Postgres)
MAX_ID = 2147483647


@router.get("/{stage_id}/track")
async def get_stage_track(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
):
    """GeoJSON нитка маршрута этапа."""
    return await PublicMapService(session).get_stage_route_geojson(stage_id)


@router.get("/{stage_id}/checkpoints")
async def get_stage_checkpoints(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
):
    """Список КП этапа (с высотами и километражом)."""
    return await PublicMapService(session).get_checkpoints(stage_id)


@router.get("/{stage_id}/positions")
async def get_stage_positions(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    since: Annotated[AwareDatetime, Query()] | None = None,
):
    """Последние координаты всех участников на этапе."""
    return await PublicMapService(session).get_positions(stage_id, since=since)


@router.get("/{stage_id}/leaders")
async def get_stage_leaders(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    discipline: str | None = Query(default=None, description="Код дисциплины"),
    as_of: Annotated[AwareDatetime, Query()] | None = None,
):
    """Рейтинг участников по судейским отметкам."""
    return await PublicMapService(session).get_leaders(stage_id, discipline=discipline, as_of=as_of)
