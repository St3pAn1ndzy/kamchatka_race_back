from enum import StrEnum


class ParticipantStatus(StrEnum):
    REGISTERED = "registered"
    ACTIVE = "active"
    FINISHED = "finished"
    WITHDRAWN = "withdrawn"
    DISQUALIFIED = "disqualified"
