from datetime import datetime
from typing import Literal

from app.enums import CheckpointKind, ParticipantStatus
from app.schemas.base import BaseSchema

FreshnessStatus = Literal["fresh", "delayed", "stale", "no_data"]


class MapPosition(BaseSchema):
    lat: float
    lon: float
    recorded_at: datetime
    average_speed_kmh: float | None = None
    km_from_start: float | None = None


class MapParticipant(BaseSchema):
    id: int
    number: int
    name: str
    discipline_id: int | None
    discipline: str | None
    status: ParticipantStatus
    freshness_status: FreshnessStatus
    position: MapPosition | None


class MapParticipantsResponse(BaseSchema):
    stage_id: int
    items: list[MapParticipant]
    total: int
    limit: int
    offset: int


class MapTrackResponse(BaseSchema):
    stage_id: int
    participant_id: int
    points: list[MapPosition]
    total: int
    limit: int
    offset: int


class MapCheckpoint(BaseSchema):
    id: int
    code: str
    name: str
    type: CheckpointKind
    description: str | None = None
    lat: float
    lon: float
    elevation: int | None = None
    km: float | None = None
    order_index: int


class MapCheckpointsResponse(BaseSchema):
    stage_id: int
    items: list[MapCheckpoint]
