"""Схемы уведомлений."""

from datetime import datetime

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
