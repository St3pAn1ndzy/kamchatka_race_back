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
    CAMP = "camp"


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


class ViewerLocationKind(StrEnum):
    """Виды зрительских локаций"""

    START = "start"
    FINISH = "finish"
    FESTIVAL = "festival"
    VIEWPOINT = "viewpoint"
    OTHER = "other"


class ViewerLocationCategory(StrEnum):
    """Категория локации для UX-фильтров (таблетки на карте)."""

    STAGES = "stages"  # Сцены (Главная сцена, Шатёр)
    AREAS = "areas"  # Площадки (Фотозона, Этнозона)
    FOOD = "food"  # Еда (Фудкорт)
    KIDS = "kids"  # Детям (Детская зона)
    OTHER = "other"  # Для всего остального (например, смотровые)


class UserFeedbackStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class UserFeedbackKind(StrEnum):
    BUG = "bug"
    IDEA = "idea"
    QUESTION = "question"
    OTHER = "other"


class ShareEventTargetKind(StrEnum):
    APP = "app"
    NEWS = "news"
    SCHEDULE_EVENT = "schedule_event"
    PARTICIPANT = "participant"
    CHECKPOINT = "checkpoint"
    VIEWER_LOCATION = "viewer_location"


class ShareEventChannel(StrEnum):
    VK = "vk"
    TELEGRAM = "telegram"
    COPY_LINK = "copy_link"
    OTHER = "other"


class PublicationStatus(StrEnum):
    """Статус публикации результатов этапа/гонки"""

    DRAFT = "draft"
    PROVISIONAL = "provisional"
    OFFICIAL = "official"


class GuestItemSection(StrEnum):
    CLOTHING = "clothing"
    SHOES = "shoes"
    EQUIPMENT = "equipment"
