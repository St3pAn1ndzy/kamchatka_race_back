from markupsafe import Markup
from sqlalchemy import select
from starlette.requests import Request

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import (
    fmt_datetime,
    fmt_notification_event,
    fmt_notification_status,
)
from app.admin_panel.utils import get_int_param
from app.db.models import FanSubscription, NotificationQueue


class FanSubscriptionAdmin(BaseAdminView, model=FanSubscription):
    name = "Подписка «Болею за»"
    name_plural = "Подписки «Болею за»"
    icon = "fa-solid fa-heart"
    category = CategoryAdminEnum.CATEGORY_COMMUNICATIONS
    category_icon = "fa-solid fa-bell"
    can_create = False
    can_edit = False
    can_delete = True

    column_list = [
        FanSubscription.id,
        FanSubscription.user,
        FanSubscription.participant,
        FanSubscription.created_at,
    ]
    column_labels = {
        FanSubscription.id: "ID",
        FanSubscription.user: "Болельщик",
        FanSubscription.participant: "Участник",
        FanSubscription.created_at: "Подписан",
    }
    column_formatters = {
        FanSubscription.user: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/user/details/{m.user.id}" class="text-primary text-decoration-none">'
                f"{m.user.first_name or '—'} {m.user.last_name or ''}</a>"
            )
            if m.user
            else "—"
        ),
        FanSubscription.participant: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary fw-bold text-decoration-none">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        FanSubscription.created_at: lambda m, a: fmt_datetime(m.created_at),
    }
    column_formatters_detail = {
        FanSubscription.user: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/user/details/{m.user.id}" class="text-primary text-decoration-none">'
                f"{m.user.first_name or '—'} {m.user.last_name or ''} (VK#{m.user.vk_user_id})</a>"
            )
            if m.user
            else "—"
        ),
        FanSubscription.participant: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary fw-bold text-decoration-none">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        FanSubscription.created_at: lambda m, a: fmt_datetime(m.created_at),
    }
    column_details_list = [
        FanSubscription.id,
        FanSubscription.user,
        FanSubscription.participant,
        FanSubscription.created_at,
    ]
    column_sortable_list = [FanSubscription.created_at]
    column_selectinload = [FanSubscription.user, FanSubscription.participant]

    # ═══ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)

        if uid := get_int_param(request, "user_id"):
            stmt = stmt.where(FanSubscription.user_id == uid)

        if pid := get_int_param(request, "participant_id"):
            stmt = stmt.where(FanSubscription.participant_id == pid)

        return stmt


class NotificationQueueAdmin(BaseAdminView, model=NotificationQueue):
    name = "Уведомление"
    name_plural = "Очередь уведомлений"
    icon = "fa-solid fa-bell"
    category = CategoryAdminEnum.CATEGORY_COMMUNICATIONS
    category_icon = "fa-solid fa-bell"
    can_create = False
    can_edit = False

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
        NotificationQueue.user: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/user/details/{m.user.id}" class="text-primary text-decoration-none">'
                f"VK#{m.user.vk_user_id}</a>"
            )
            if m.user
            else "—"
        ),
        NotificationQueue.status: lambda m, a: fmt_notification_status(m.status),
        NotificationQueue.event_type: lambda m, a: fmt_notification_event(m.event_type),
        NotificationQueue.sent_at: lambda m, a: fmt_datetime(m.sent_at),
        NotificationQueue.title: lambda m, a: Markup(
            f'<a href="/admin-panel/notification-queue/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.title}</a>'
        ),
    }
    column_formatters_detail = {
        NotificationQueue.scheduled_at: lambda m, a: fmt_datetime(m.scheduled_at),
        NotificationQueue.user: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/user/details/{m.user.id}" class="text-primary text-decoration-none">'
                f"{m.user.first_name or '—'} {m.user.last_name or ''} (VK#{m.user.vk_user_id})</a>"
            )
            if m.user
            else "—"
        ),
        NotificationQueue.status: lambda m, a: fmt_notification_status(m.status),
        NotificationQueue.event_type: lambda m, a: fmt_notification_event(m.event_type),
        NotificationQueue.sent_at: lambda m, a: fmt_datetime(m.sent_at),
    }
    column_details_list = [
        NotificationQueue.scheduled_at,
        NotificationQueue.user,
        NotificationQueue.event_type,
        NotificationQueue.status,
        NotificationQueue.title,
        NotificationQueue.body,
        NotificationQueue.sent_at,
    ]
    column_default_sort = (NotificationQueue.scheduled_at, True)
    column_selectinload = [NotificationQueue.user]

    # ═══ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if uid := get_int_param(request, "user_id"):
            stmt = stmt.where(NotificationQueue.user_id == uid)

        if status := q.get("status"):
            stmt = stmt.where(NotificationQueue.status == status)

        if event_type := q.get("event_type"):
            stmt = stmt.where(NotificationQueue.event_type == event_type)

        return stmt
