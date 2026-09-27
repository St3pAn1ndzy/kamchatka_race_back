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


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationEventType(StrEnum):
    STAGE_START = "stage_start"
    STAGE_FINISH = "stage_finish"
    CHECKPOINT_PASSED = "checkpoint_passed"
    LEADER_CHANGED = "leader_changed"
    PARTICIPANT_FINISHED = "participant_finished"
    BROADCAST = "broadcast"
    FAVORITE_UPDATE = "favorite_update"


class NewsSource(StrEnum):
    MANUAL = "manual"
    VK = "vk"
