"""Публичный API для экрана карты и трекинга этапов."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.services.public_map import PublicMapService

router = APIRouter(prefix="/stages", tags=["stages"])


@router.get("/{stage_id}/track")
async def get_stage_track(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0)],
):
    """GeoJSON нитка маршрута этапа."""
    return await PublicMapService(session).get_stage_route_geojson(stage_id)


@router.get("/{stage_id}/checkpoints")
async def get_stage_checkpoints(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0)],
):
    """Список КП этапа (с высотами и километражом)."""
    # У тебя уже есть метод get_checkpoints, он отдает MapCheckpointsResponse
    return await PublicMapService(session).get_checkpoints(stage_id)


@router.get("/{stage_id}/positions")
async def get_stage_positions(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0)],
    since: datetime | None = Query(default=None, description="Только точки новее этой даты"),
):
    """Последние координаты всех участников на этапе."""
    return await PublicMapService(session).get_positions(stage_id, since=since)


@router.get("/{stage_id}/leaders")
async def get_stage_leaders(
    session: SessionDep,
    stage_id: Annotated[int, Path(gt=0)],
    discipline: str | None = Query(default=None, description="Код дисциплины"),
    as_of: datetime | None = Query(default=None, description="На какое время актуален рейтинг"),
):
    """Рейтинг участников по судейским отметкам."""
    return await PublicMapService(session).get_leaders(stage_id, discipline=discipline, as_of=as_of)
