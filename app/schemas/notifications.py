"""Схемы уведомлений."""

from datetime import datetime

from pydantic import Field

from app.enums import NotificationEventType, NotificationStatus
from app.schemas.base import BaseSchema


class NotificationItem(BaseSchema):
    """Одно уведомление."""

    id: int
    event_type: NotificationEventType
    title: str
    body: str
    status: NotificationStatus
    scheduled_at: datetime
    sent_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseSchema):
    """История уведомлений пользователя."""

    items: list[NotificationItem]
    total: int


class NotificationPreviewResponse(BaseSchema):
    """Пример текста уведомления."""

    event_type: NotificationEventType
    title: str
    body: str


class NotificationPreviewListResponse(BaseSchema):
    """Список preview для экрана настроек."""

    items: list[NotificationPreviewResponse]


class NotificationPreferenceOut(BaseSchema):
    """Настройка по одному типу события (заглушка, будет в след. эпике)."""

    event_type: NotificationEventType
    title: str
    enabled: bool


class NotificationSettingsResponse(BaseSchema):
    """Текущие настройки уведомлений пользователя."""

    notifications_allowed: bool
    vk_limit_note: str = "VK ограничивает: до 2 уведомлений в час и до 10 в сутки"
    preferences: list[NotificationPreferenceOut] = Field(default_factory=list)


class NotificationSettingsUpdate(BaseSchema):
    """Изменение настроек уведомлений."""

    notifications_allowed: bool | None = Field(
        default=None,
        description="Согласие на push-уведомления",
    )
