"""SQLAdmin — веб-панель администраторов."""

from sqladmin import ModelView

from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.audit_log import AuditLog
from app.db.models.discipline import Discipline
from app.db.models.fun_subscription import FanSubscription
from app.db.models.participant import Participant
from app.db.models.season import Season
from app.db.models.stage import Stage


class AdminAccountAdmin(ModelView, model=AdminAccount):
    name = "Администратор"
    name_plural = "Администраторы"
    icon = "fa-solid fa-user-shield"
    category = "Система"
    category_icon = "fa-solid fa-gear"
    # password_hash не показываем — даже админам.
    column_list = [
        AdminAccount.id,
        AdminAccount.login,
        AdminAccount.vk_user_id,
        AdminAccount.display_name,
        AdminAccount.is_active,
        AdminAccount.created_at,
    ]
    column_searchable_list = [AdminAccount.login, AdminAccount.display_name]


class SeasonAdmin(ModelView, model=Season):
    name = "Сезон"
    name_plural = "Сезоны"
    icon = "fa-solid fa-calendar"
    category = "Событие"
    category_icon = "fa-solid fa-calendar-days"
    column_list = [
        Season.id,
        Season.year,
        Season.title,
        Season.starts_at,
        Season.ends_at,
        Season.is_active,
    ]
    column_sortable_list = [Season.year, Season.starts_at]


class DisciplineAdmin(ModelView, model=Discipline):
    name = "Дисциплина"
    name_plural = "Дисциплины"
    icon = "fa-solid fa-list"
    category = "Событие"
    category_icon = "fa-solid fa-calendar-days"
    column_list = [
        Discipline.id,
        Discipline.season_id,
        Discipline.code,
        Discipline.name,
        Discipline.sort_order,
        Discipline.is_active,
    ]
    column_searchable_list = [Discipline.code, Discipline.name]
    column_sortable_list = [Discipline.sort_order, Discipline.name]


class StageAdmin(ModelView, model=Stage):
    name = "Этап"
    name_plural = "Этапы"
    icon = "fa-solid fa-route"
    category = "Событие"
    category_icon = "fa-solid fa-calendar-days"
    column_list = [
        Stage.id,
        Stage.season_id,
        Stage.number,
        Stage.name,
        Stage.start_time,
        Stage.finish_time,
        Stage.status,
        Stage.results_publication,
    ]
    column_searchable_list = [Stage.name]
    column_sortable_list = [Stage.order_index, Stage.number, Stage.start_time]


class AdminSessionAdmin(ModelView, model=AdminSession):
    name = "Сессия"
    name_plural = "Сессии админов"
    icon = "fa-solid fa-key"
    category = "Система"
    category_icon = "fa-solid fa-gear"
    # Сессии создаются через login. Вручную — только просмотр.
    can_create = False
    can_edit = False
    column_list = [
        AdminSession.id,
        AdminSession.admin_id,
        AdminSession.expires_at,
        AdminSession.revoked_at,
        AdminSession.created_at,
    ]


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Аудит"
    name_plural = "Журнал аудита"
    icon = "fa-solid fa-clipboard-list"
    category = "Система"
    category_icon = "fa-solid fa-gear"
    # Журнал — только просмотр.
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        AuditLog.id,
        AuditLog.admin_id,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.created_at,
    ]
    column_sortable_list = [AuditLog.created_at]
    column_searchable_list = [AuditLog.action, AuditLog.entity_type]


class ParticipantAdmin(ModelView, model=Participant):
    name = "Участник"
    name_plural = "Участники"
    icon = "fa-solid fa-user"
    category = "Участники"
    category_icon = "fa-solid fa-users"
    column_list = [
        Participant.id,
        Participant.name,
        Participant.number,
        Participant.region,
        Participant.discipline_id,
        Participant.status,
        Participant.dogs_count,
    ]
    column_searchable_list = [
        Participant.name,
        Participant.number,
    ]
    column_sortable_list = [
        Participant.number,
        Participant.name,
    ]


class FanSubscriptionAdmin(ModelView, model=FanSubscription):
    name = "Подписка «Болею за»"
    name_plural = "Подписки «Болею за»"
    icon = "fa-solid fa-heart"
    category = "Коммуникации"
    category_icon = "fa-solid fa-bell"
    # Только просмотр — создаётся через API.
    can_create = False
    can_edit = False
    column_list = [
        FanSubscription.id,
        FanSubscription.user_id,
        FanSubscription.participant_id,
        FanSubscription.created_at,
    ]
    column_sortable_list = [FanSubscription.created_at]


VIEWS: list[type[ModelView]] = [
    AdminAccountAdmin,
    AdminSessionAdmin,
    AuditLogAdmin,
    ParticipantAdmin,
    FanSubscriptionAdmin,
    SeasonAdmin,
    DisciplineAdmin,
    StageAdmin,
]
