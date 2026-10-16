from sqladmin import ModelView
from wtforms import SelectField
from wtforms.validators import NumberRange

from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime, fmt_participant_status
from app.db.models import Device, Participant
from app.enums import ParticipantStatus

_LABELS = {
    ParticipantStatus.REGISTERED: "Заявлен",
    ParticipantStatus.ACTIVE: "Активен",
    ParticipantStatus.FINISHED: "Финишировал",
    ParticipantStatus.WITHDRAWN: "Сошёл",
    ParticipantStatus.DISQUALIFIED: "Дисквалифицирован",
}


class DeviceAdmin(ModelView, model=Device):
    name = "Трекер"
    name_plural = "Трекеры"
    icon = "fa-solid fa-satellite-dish"
    category = CategoryAdminEnum.CATEGORY_PARTICIPANTS
    category_icon = "fa-solid fa-users"

    column_list = [
        Device.iridium_number,
        Device.imei,
        Device.participant,
        Device.stage,
        Device.is_active,
        Device.battery_percent,
        Device.sos_active,
        Device.last_message_at,
    ]
    column_labels = {
        Device.iridium_number: "Iridium №",
        Device.imei: "IMEI",
        Device.participant: "Участник",
        Device.stage: "Этап",
        Device.is_active: "Активен",
        Device.battery_percent: "Батарея, %",
        Device.sos_active: "SOS",
        Device.last_message_at: "Последний сигнал",
    }
    column_formatters = {
        Device.participant: lambda m, a: (
            f"№{m.participant.number} {m.participant.name}" if m.participant else "—"
        ),
        Device.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        Device.is_active: lambda m, a: fmt_bool(m.is_active),
        Device.sos_active: lambda m, a: fmt_bool(m.sos_active),
        Device.last_message_at: lambda m, a: fmt_datetime(m.last_message_at),
    }
    column_default_sort = (Device.iridium_number, False)
    column_searchable_list = [Device.iridium_number, Device.imei]

    can_delete = False

    form_columns = [
        Device.iridium_number,
        Device.imei,
        Device.name,
        Device.participant,
        Device.stage,
        Device.is_active,
    ]
    form_widget_args = {
        Device.iridium_number: {"placeholder": "001"},
        Device.imei: {"placeholder": "300234560000001"},
        Device.name: {"placeholder": "Трекер №001"},
    }


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
