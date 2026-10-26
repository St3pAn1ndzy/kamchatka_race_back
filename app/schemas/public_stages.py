"""Схемы публичного API для экрана карты и трекинга этапов."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema


class StageTrackResponse(BaseSchema):
    """GeoJSON LineString с ниткой маршрута этапа."""

    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(..., description="Массив координат [[lon, lat], ...]")


class CheckpointPublicResponse(BaseSchema):
    """КП этапа с высотами и километражом."""

    id: int
    code: str
    name: str
    type: str
    lat: float
    lon: float
    km: float | None = None
    elevation: int | None = None
    order_index: int
    description: str | None = None


class PositionPublicResponse(BaseSchema):
    """Последняя подтвержденная точка участника."""

    participant_id: int
    bib: int
    lat: float
    lon: float
    recorded_at: datetime
    source: str = "iridium"
    last_cp_id: int | None = None
    freshness: str | None = None


class LeaderRow(BaseSchema):
    participant_id: int
    bib: int
    place: int


class LeadersResponse(BaseSchema):
    as_of: datetime
    leaders: list[LeaderRow]
