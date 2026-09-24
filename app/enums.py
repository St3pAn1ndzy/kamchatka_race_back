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


class RaceState(StrEnum):
    UPCOMING = "upcoming"
    LIVE = "live"
    FINISHED = "finished"
