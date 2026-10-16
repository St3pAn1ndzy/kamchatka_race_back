"""SQLAdmin — веб-панель администраторов."""

from sqladmin import ModelView
from wtforms import SelectField
from wtforms.validators import NumberRange

from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import (
    fmt_bool,
    fmt_datetime,
    fmt_participant_status,
    fmt_publication,
    fmt_stage_status,
)
from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.audit_log import AuditLog
from app.db.models.discipline import Discipline
from app.db.models.fun_subscription import FanSubscription
from app.db.models.participant import Participant
from app.db.models.season import Season
from app.db.models.stage import Stage
from app.enums import ParticipantStatus, StageStatus, PublicationStatus

_LABELS = {
    ParticipantStatus.REGISTERED: "Заявлен",
    ParticipantStatus.ACTIVE: "Активен",
    ParticipantStatus.FINISHED: "Финишировал",
    ParticipantStatus.WITHDRAWN: "Сошёл",
    ParticipantStatus.DISQUALIFIED: "Дисквалифицирован",
}

_LABELS_STAGE = {
    StageStatus.PLANNED: "Запланирован",
    StageStatus.ACTIVE: "Идёт",
    StageStatus.FINISHED: "Завершён",
}

_LABELS_RESULTS_PUB = {
    PublicationStatus.DRAFT: "Черновик",
    PublicationStatus.PROVISIONAL: "Предварительно",
    PublicationStatus.OFFICIAL: "Официально",
}


class AdminAccountAdmin(ModelView, model=AdminAccount):
    name = "Администратор"
    name_plural = "Администраторы"
    icon = "fa-solid fa-user-shield"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
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
    column_formatters = {
        AdminAccount.is_active: lambda m, a: fmt_bool(m.is_active),
    }
    column_searchable_list = [AdminAccount.login, AdminAccount.display_name]

    can_delete = False

    form_columns = [
        AdminAccount.login,
        AdminAccount.display_name,
        AdminAccount.vk_user_id,
        AdminAccount.is_active,
    ]
    form_widget_args = {
        AdminAccount.login: {"placeholder": "admin"},
        AdminAccount.display_name: {"placeholder": "Главный администратор"},
        AdminAccount.vk_user_id: {"placeholder": "123456 (опционально)"},
    }


class SeasonAdmin(ModelView, model=Season):
    name = "Сезон"
    name_plural = "Сезоны"
    icon = "fa-solid fa-calendar"
    category = CategoryAdminEnum.CATEGORY_EVENT
    category_icon = "fa-solid fa-calendar-days"
    column_list = [
        Season.id,
        Season.year,
        Season.title,
        Season.starts_at,
        Season.ends_at,
        Season.is_active,
    ]
    column_formatters = {
        Season.is_active: lambda m, a: fmt_bool(m.is_active),
    }
    column_sortable_list = [Season.year, Season.starts_at]

    can_delete = False

    form_columns = [
        Season.year,
        Season.title,
        Season.starts_at,
        Season.ends_at,
        Season.is_active,
    ]
    form_args = {
        "year": {"validators": [NumberRange(min=2000, max=2100)]},
    }


class DisciplineAdmin(ModelView, model=Discipline):
    name = "Дисциплина"
    name_plural = "Дисциплины"
    icon = "fa-solid fa-list"
    category = CategoryAdminEnum.CATEGORY_EVENT
    category_icon = "fa-solid fa-calendar-days"
    column_list = [
        Discipline.id,
        Discipline.season,
        Discipline.code,
        Discipline.name,
        Discipline.sort_order,
        Discipline.is_active,
    ]
    column_formatters = {
        Discipline.is_active: lambda m, a: fmt_bool(m.is_active),
        Discipline.season: lambda m, a: m.season.title if m.season else "—",
    }
    column_searchable_list = [Discipline.code, Discipline.name]
    column_sortable_list = [Discipline.sort_order, Discipline.name]

    can_delete = False

    form_columns = [
        Discipline.season,
        Discipline.code,
        Discipline.name,
        Discipline.sort_order,
        Discipline.is_active,
    ]
    form_widget_args = {
        Discipline.code: {"placeholder": "long / middle / sprint"},
        Discipline.name: {"placeholder": "Длинная"},
    }
    form_args = {
        "sort_order": {"validators": [NumberRange(min=0)]},
    }


class StageAdmin(ModelView, model=Stage):
    name = "Этап"
    name_plural = "Этапы"
    icon = "fa-solid fa-route"
    category = CategoryAdminEnum.CATEGORY_EVENT
    category_icon = "fa-solid fa-calendar-days"
    column_list = [
        Stage.number,
        Stage.name,
        Stage.season,
        Stage.distance_km,
        Stage.start_time,
        Stage.status,
        Stage.results_publication,
    ]
    column_labels = {
        Stage.number: "№",
        Stage.name: "Название",
        Stage.season: "Сезон",
        Stage.distance_km: "Дистанция, км",
        Stage.start_time: "Старт",
        Stage.status: "Статус",
        Stage.results_publication: "Результаты",
    }
    column_formatters = {
        Stage.season: lambda m, a: m.season.title if m.season else "—",
        Stage.start_time: lambda m, a: fmt_datetime(m.start_time),
        Stage.status: lambda m, a: fmt_stage_status(m.status),
        Stage.results_publication: lambda m, a: fmt_publication(m.results_publication),
    }
    column_searchable_list = [Stage.name]
    column_sortable_list = [Stage.order_index, Stage.number, Stage.start_time]

    can_delete = False

    form_columns = [
        Stage.season,
        Stage.number,
        Stage.name,
        Stage.distance_km,
        Stage.start_time,
        Stage.finish_time,
        Stage.order_index,
        Stage.tracker_interval_seconds,
        Stage.status,
        Stage.results_publication,
    ]
    form_widget_args = {
        Stage.name: {"placeholder": "Этап 1. Старт — КП-2"},
        Stage.distance_km: {"placeholder": "100.0"},
        Stage.order_index: {"placeholder": "0"},
    }
    form_args = {
        "distance_km": {"validators": [NumberRange(min=0, max=2000)]},
        "order_index": {"validators": [NumberRange(min=0)]},
        "tracker_interval_seconds": {"validators": [NumberRange(min=15, max=86400)]},
        "status": {"choices": [(s.value, _LABELS_STAGE[s]) for s in StageStatus]},
        "results_publication": {
            "choices": [(s.value, _LABELS_RESULTS_PUB[s]) for s in PublicationStatus]
        },
    }

    form_overrides = {
        "status": SelectField,
        "results_publication": SelectField,
    }


class AdminSessionAdmin(ModelView, model=AdminSession):
    name = "Сессия"
    name_plural = "Сессии админов"
    icon = "fa-solid fa-key"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    # Сессии создаются через login. Вручную — только просмотр.
    can_create = False
    can_edit = False
    column_list = [
        AdminSession.admin,
        AdminSession.created_at,
        AdminSession.expires_at,
        AdminSession.revoked_at,
    ]
    column_labels = {
        AdminSession.admin: "Администратор",
        AdminSession.created_at: "Создана",
        AdminSession.expires_at: "Истекает",
        AdminSession.revoked_at: "Отозвана",
    }
    column_formatters = {
        AdminSession.admin: lambda m, a: m.admin.login if m.admin else "—",
        AdminSession.created_at: lambda m, a: fmt_datetime(m.created_at),
        AdminSession.expires_at: lambda m, a: fmt_datetime(m.expires_at),
        AdminSession.revoked_at: lambda m, a: fmt_datetime(m.revoked_at),
    }


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Запись аудита"
    name_plural = "Журнал аудита"
    icon = "fa-solid fa-clipboard-list"
    category = CategoryAdminEnum.CATEGORY_SYSTEM
    category_icon = "fa-solid fa-gear"
    # Журнал — только просмотр.
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        AuditLog.id,
        AuditLog.admin,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.created_at,
    ]
    column_formatters = {
        AuditLog.admin: lambda m, a: m.admin.login if m.admin else "—",
    }
    column_sortable_list = [AuditLog.created_at]
    column_searchable_list = [AuditLog.action, AuditLog.entity_type]


class ParticipantAdmin(ModelView, model=Participant):
    name = "Участник"
    name_plural = "Участники"
    icon = "fa-solid fa-user"
    category = CategoryAdminEnum.CATEGORY_PARTICIPANTS
    category_icon = "fa-solid fa-users"

    column_list = [
        Participant.number,
        Participant.name,
        Participant.region,
        Participant.discipline_ref,
        Participant.status,
        Participant.dogs_count,
    ]
    column_labels = {
        Participant.number: "№",
        Participant.name: "Имя",
        Participant.region: "Регион",
        Participant.discipline_ref: "Дисциплина",
        Participant.status: "Статус",
        Participant.dogs_count: "Собак",
        Participant.bio: "Биография",
        Participant.photo_url: "Фото (URL)",
    }
    column_formatters = {
        Participant.discipline_ref: lambda m, a: m.discipline_ref.name if m.discipline_ref else "—",
        Participant.status: lambda m, a: fmt_participant_status(m.status),
    }
    column_searchable_list = [Participant.name, Participant.number]
    column_sortable_list = [Participant.number, Participant.name]

    can_delete = False

    form_columns = [
        Participant.number,
        Participant.name,
        Participant.region,
        Participant.discipline_ref,
        Participant.dogs_count,
        Participant.status,
        Participant.bio,
        Participant.photo_url,
    ]
    form_widget_args = {
        Participant.name: {"placeholder": "Иванов Иван"},
        Participant.region: {"placeholder": "Камчатский край"},
        Participant.bio: {"placeholder": "Краткая биография каюра (до 1000 символов)"},
        Participant.photo_url: {"placeholder": "https://..."},
    }
    form_overrides = {
        "status": SelectField,
    }
    form_args = {
        "dogs_count": {"validators": [NumberRange(min=1, max=20)]},
        "number": {"validators": [NumberRange(min=1)]},
        "status": {
            "choices": [(s.value, _LABELS[s]) for s in ParticipantStatus],
        },
    }


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
