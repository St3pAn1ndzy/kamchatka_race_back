from enum import StrEnum


class ParticipantStatus(StrEnum):
    REGISTERED = "registered"
    ACTIVE = "active"
    FINISHED = "finished"
    WITHDRAWN = "withdrawn"
    DISQUALIFIED = "disqualified"


class StageStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    FINISHED = "finished"


class ScheduleKind(StrEnum):
    """Виды событий в программе фестиваля"""

    # По необходимости можно добавить новые виды событий,
    # например: workshop, concert, meeting и т.д.
    RACE = "race"
    CULTURAL = "cultural"
    OTHER = "other"


class RaceState(StrEnum):
    UPCOMING = "upcoming"
    LIVE = "live"
    FINISHED = "finished"


class CheckpointKind(StrEnum):
    START = "start"
    FINISH = "finish"
    CHECKPOINT = "checkpoint"
