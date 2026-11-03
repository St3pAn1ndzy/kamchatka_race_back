"""Схемы результатов гонки."""

from datetime import datetime

from app.enums import CheckpointKind, PublicationStatus
from app.schemas.base import BaseSchema


class ControlTimeEntry(BaseSchema):
    """Отметка участника на контрольном пункте."""

    checkpoint_id: int
    checkpoint_code: str
    checkpoint_name: str
    checkpoint_kind: CheckpointKind
    mark_time: datetime
    penalty_minutes: int = 0
    mandatory_stop_minutes: int = 0


class StageProtocolRow(BaseSchema):
    """Строка протокола этапа."""

    participant_id: int
    participant_name: str
    participant_number: int
    discipline_id: int | None = None
    discipline_code: str | None = None
    discipline_name: str | None = None
    start_time: datetime | None = None
    finish_time: datetime | None = None
    elapsed_time_seconds: int | None = None
    total_penalty_seconds: int = 0
    total_mandatory_stop_seconds: int = 0
    final_time_seconds: int | None = None
    position: int | None = None


class StageProtocol(BaseSchema):
    """Протокол этапа."""

    stage_id: int
    stage_name: str
    publication: PublicationStatus
    rows: list[StageProtocolRow]


class StandingRow(BaseSchema):
    """Строка сводной таблицы."""

    participant_id: int
    participant_name: str
    participant_number: int
    discipline_id: int | None = None
    discipline_code: str | None = None
    discipline_name: str | None = None
    total_penalty_seconds: int = 0
    total_mandatory_stop_seconds: int = 0
    final_time_seconds: int | None = None
    position: int | None = None
    stages_finished: int = 0


class RaceStandings(BaseSchema):
    """Сводная таблица лидеров."""

    mode: str = "official"
    rows: list[StandingRow]


class LeaderboardEntry(BaseSchema):
    """Строка таблицы лидеров."""

    participant_id: int
    participant_name: str
    participant_number: int
    discipline_id: int | None = None
    discipline_code: str | None = None
    discipline_name: str | None = None
    position: int
    final_time_seconds: int | None = None
    stages_finished: int = 0
    mode: str = "official"
