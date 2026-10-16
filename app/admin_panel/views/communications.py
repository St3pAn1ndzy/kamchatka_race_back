from sqladmin import ModelView

from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_datetime, fmt_notification_event, fmt_notification_status
from app.db.models import FanSubscription, NotificationQueue


class FanSubscriptionAdmin(ModelView, model=FanSubscription):
    name = "Подписка «Болею за»"
    name_plural = "Подписки «Болею за»"
    icon = "fa-solid fa-heart"
    category = CategoryAdminEnum.CATEGORY_COMMUNICATIONS
    category_icon = "fa-solid fa-bell"
    # Только просмотр — создаётся через API.
    can_create = False
    can_edit = False
    column_list = [
        FanSubscription.id,
        FanSubscription.user,
        FanSubscription.participant,
        FanSubscription.created_at,
    ]
    column_formatters = {
        FanSubscription.user: lambda m, a: m.user.first_name if m.user.first_name else "—",
        FanSubscription.participant: lambda m, a: m.participant.name if m.participant else "—",
    }
    column_sortable_list = [FanSubscription.created_at]


class NotificationQueueAdmin(ModelView, model=NotificationQueue):
    name = "Уведомление"
    name_plural = "Очередь уведомлений"
    icon = "fa-solid fa-bell"
    category = CategoryAdminEnum.CATEGORY_COMMUNICATIONS
    category_icon = "fa-solid fa-bell"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        NotificationQueue.scheduled_at,
        NotificationQueue.user,
        NotificationQueue.event_type,
        NotificationQueue.status,
        NotificationQueue.title,
        NotificationQueue.sent_at,
    ]
    column_labels = {
        NotificationQueue.scheduled_at: "Запланировано",
        NotificationQueue.user: "Пользователь",
        NotificationQueue.event_type: "Событие",
        NotificationQueue.status: "Статус",
        NotificationQueue.title: "Заголовок",
        NotificationQueue.sent_at: "Отправлено",
    }
    column_formatters = {
        NotificationQueue.scheduled_at: lambda m, a: fmt_datetime(m.scheduled_at),
        NotificationQueue.user: lambda m, a: f"#{m.user.vk_user_id}" if m.user else "—",
        NotificationQueue.status: lambda m, a: fmt_notification_status(m.status),
        NotificationQueue.event_type: lambda m, a: fmt_notification_event(m.event_type),
        NotificationQueue.sent_at: lambda m, a: fmt_datetime(m.sent_at),
    }
    column_default_sort = (NotificationQueue.scheduled_at, True)
