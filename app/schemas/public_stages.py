"""Схемы публичного API для экрана карты и трекинга."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema


# Трек маршрута (GeoJSON)
class StageTrackResponse(BaseSchema):
    """GeoJSON LineString с треком маршрута этапа."""

    type: Literal["LineString"] = "LineString"

    # В GeoJSON координаты всегда идут в порядке [Долгота, Широта]
    coordinates: list[list[float]] = Field(
        description="Массив координат [[lon, lat], [lon, lat], ...]"
    )


# Контрольные пункты
class CheckpointPublicResponse(BaseSchema):
    """КП этапа с высотами и километражом."""

    id: int
    name: str

    # Фронтендер просит 'type', но в БД у нас 'kind'. Делаем алиас.
    type: str = Field(alias="kind")

    lat: float
    lon: float
    km: float | None = Field(default=None, alias="km_from_race_start")
    elevation: int | None = Field(default=None, alias="altitude")


# Текущие позиции участников
class PositionPublicResponse(BaseSchema):
    """Последняя подтвержденная точка участника."""

    participant_id: int
    bib: int = Field(alias="participant_number")  # Стартовый номер
    lat: float
    lon: float
    recorded_at: datetime
    source: str = "iridium"  # Источник данных

    # ID последнего пройденного КП
    last_cp_id: int | None = None


# Лидеры / Рейтинг
class LeaderRow(BaseSchema):
    """Строка рейтинга лидеров."""

    participant_id: int
    bib: int
    place: int


class LeadersResponse(BaseSchema):
    """Ответ с рейтингом и временем актуальности."""

    as_of: datetime
    leaders: list[LeaderRow]
