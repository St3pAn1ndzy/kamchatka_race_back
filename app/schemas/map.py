"""Схемы публичной карты гонки"""

from datetime import datetime

from app.enums import CheckpointKind, ParticipantStatus
from app.schemas.base import BaseSchema


class MapTrackPoint(BaseSchema):
    """Последняя точка участника на карте"""

    lat: float
    lon: float
    recorded_at: datetime
    received_at: datetime
    course_deg: float | None = None
    source_speed: float | None = None
    average_speed_kmh: float | None = None
    km_from_start: float | None = None


class MapParticipant(BaseSchema):
    """Участник и его последняя позиция для карты"""

    id: int
    name: str
    number: int
    region: str | None = None
    discipline: str
    photo_url: str | None = None
    status: ParticipantStatus
    latest_point: MapTrackPoint | None = None


class MapEntryTrackPoint(BaseSchema):
    """Точка трека участника для линии на карте"""

    id: int
    stage_id: int | None = None
    lat: float
    lon: float
    altitude: float | None = None
    course_deg: float | None = None
    source_speed: float | None = None
    average_speed_kmh: float | None = None
    km_from_start: float | None = None
    recorded_at: datetime
    received_at: datetime


class MapEntryTrackResponse(BaseSchema):
    """Трек одного участника для карты"""

    participant_id: int
    points: list[MapEntryTrackPoint]


class MapCheckpoint(BaseSchema):
    """Контрольная точка для карты"""

    id: int
    stage_id: int
    code: str
    name: str
    kind: CheckpointKind
    description: str | None = None
    lat: float
    lon: float
    altitude: int | None = None
    km_from_race_start: float | None = None
    order_index: int
    has_judge: bool
