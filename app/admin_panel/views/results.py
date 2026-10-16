from sqladmin import ModelView
from wtforms.validators import NumberRange

from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.db.models import OfficialMark, TrackPoint


class OfficialMarkAdmin(ModelView, model=OfficialMark):
    name = "Отметка"
    name_plural = "Отметки"
    icon = "fa-solid fa-stopwatch"
    category = CategoryAdminEnum.CATEGORY_RESULTS
    category_icon = "fa-solid fa-trophy"

    column_list = [
        OfficialMark.mark_time,
        OfficialMark.participant,
        OfficialMark.checkpoint,
        OfficialMark.penalty_minutes,
        OfficialMark.mandatory_stop_minutes,
        OfficialMark.is_cancelled,
        OfficialMark.entered_by,
    ]
    column_labels = {
        OfficialMark.mark_time: "Время",
        OfficialMark.participant: "Участник",
        OfficialMark.checkpoint: "КП",
        OfficialMark.penalty_minutes: "Штраф, мин",
        OfficialMark.mandatory_stop_minutes: "Остановка, мин",
        OfficialMark.is_cancelled: "Отменена",
        OfficialMark.entered_by: "Судья",
    }
    column_formatters = {
        OfficialMark.mark_time: lambda m, a: fmt_datetime(m.mark_time),
        OfficialMark.participant: lambda m, a: (
            f"№{m.participant.number} {m.participant.name}" if m.participant else "—"
        ),
        OfficialMark.checkpoint: lambda m, a: (
            f"{m.checkpoint.code} — {m.checkpoint.name}" if m.checkpoint else "—"
        ),
        OfficialMark.is_cancelled: lambda m, a: fmt_bool(m.is_cancelled),
        OfficialMark.entered_by: lambda m, a: m.entered_by.login if m.entered_by else "—",
    }
    column_default_sort = (OfficialMark.mark_time, True)
    column_searchable_list = [OfficialMark.comment]

    # Отметку нельзя редактировать или удалять.
    # Исправление — через API (correct), старые помечаются is_cancelled.
    can_edit = False
    can_delete = False

    form_columns = [
        OfficialMark.participant,
        OfficialMark.checkpoint,
        OfficialMark.mark_time,
        OfficialMark.penalty_minutes,
        OfficialMark.mandatory_stop_minutes,
        OfficialMark.comment,
    ]
    form_widget_args = {
        OfficialMark.comment: {"placeholder": "Комментарий судьи"},
    }
    form_args = {
        "penalty_minutes": {"validators": [NumberRange(min=0, max=600)]},
        "mandatory_stop_minutes": {"validators": [NumberRange(min=0, max=600)]},
    }


class TrackPointAdmin(ModelView, model=TrackPoint):
    name = "Точка трека"
    name_plural = "Точки трека"
    icon = "fa-solid fa-location-dot"
    category = CategoryAdminEnum.CATEGORY_RESULTS
    category_icon = "fa-solid fa-trophy"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        TrackPoint.recorded_at,
        TrackPoint.participant,
        TrackPoint.stage,
        TrackPoint.lat,
        TrackPoint.lon,
        TrackPoint.km_from_start,
        TrackPoint.average_speed_kmh,
        TrackPoint.is_confirmed,
    ]
    column_labels = {
        TrackPoint.recorded_at: "Время GPS",
        TrackPoint.participant: "Участник",
        TrackPoint.stage: "Этап",
        TrackPoint.lat: "Широта",
        TrackPoint.lon: "Долгота",
        TrackPoint.km_from_start: "Км",
        TrackPoint.average_speed_kmh: "Скорость, км/ч",
        TrackPoint.is_confirmed: "Подтверждена",
    }
    column_formatters = {
        TrackPoint.recorded_at: lambda m, a: fmt_datetime(m.recorded_at),
        TrackPoint.participant: lambda m, a: f"№{m.participant.number}" if m.participant else "—",
        TrackPoint.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        TrackPoint.is_confirmed: lambda m, a: fmt_bool(m.is_confirmed),
    }
    column_default_sort = (TrackPoint.recorded_at, True)
