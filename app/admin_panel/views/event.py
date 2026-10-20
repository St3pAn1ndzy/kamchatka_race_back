"""Views для сущностей события: сезоны, дисциплины, этапы, КП."""

from starlette.requests import Request
from wtforms import SelectField
from wtforms.validators import NumberRange

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import (
    fmt_bool,
    fmt_checkpoint_kind,
    fmt_datetime,
    fmt_publication,
    fmt_stage_status,
)
from app.db.models import Checkpoint, Discipline, Season, Stage
from app.enums import PublicationStatus, StageStatus
from app.services.cache import cache

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


class CheckpointAdmin(BaseAdminView, model=Checkpoint):
    name = "Контрольный пункт"
    name_plural = "Контрольные пункты"
    icon = "fa-solid fa-flag-checkered"
    category = CategoryAdminEnum.CATEGORY_EVENT
    category_icon = "fa-solid fa-calendar-days"

    column_list = [
        Checkpoint.stage,
        Checkpoint.code,
        Checkpoint.name,
        Checkpoint.kind,
        Checkpoint.km_from_race_start,
        Checkpoint.has_judge,
        Checkpoint.is_public,
    ]
    column_labels = {
        Checkpoint.stage: "Этап",
        Checkpoint.code: "Код",
        Checkpoint.name: "Название",
        Checkpoint.kind: "Тип",
        Checkpoint.km_from_race_start: "Км от старта",
        Checkpoint.has_judge: "Судья",
        Checkpoint.is_public: "Публичный",
    }
    column_formatters = {
        Checkpoint.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        Checkpoint.has_judge: lambda m, a: fmt_bool(m.has_judge),
        Checkpoint.is_public: lambda m, a: fmt_bool(m.is_public),
        Checkpoint.kind: lambda m, a: fmt_checkpoint_kind(m.kind),
    }
    column_default_sort = (Checkpoint.km_from_race_start, False)

    column_selectinload = [Checkpoint.stage]

    form_overrides = {"kind": SelectField}
    form_args = {
        "kind": {
            "choices": [
                ("start", "Старт"),
                ("checkpoint", "Контрольный пункт"),
                ("finish", "Финиш"),
            ],
        },
    }


class DisciplineAdmin(BaseAdminView, model=Discipline):
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

    column_selectinload = [Discipline.season]

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


class SeasonAdmin(BaseAdminView, model=Season):
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


class StageAdmin(BaseAdminView, model=Stage):
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

    column_selectinload = [Stage.season]

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

    async def after_model_change(
        self, data: dict, model: Stage, is_created: bool, request: Request
    ) -> None:
        """Инвалидация кэша после изменения или создания этапа."""
        await cache.invalidate_pattern("public:stages:*")
        await cache.invalidate_pattern("public:disciplines:*")
        await cache.invalidate_pattern(f"public:map:model:{model.id}:*")
        await cache.delete(f"public:map:checkpoint:{model.id}")
        await cache.invalidate_pattern(f"public:map:track:{model.id}:*")
        await cache.delete(f"public:results:stage:{model.id}")
        await cache.delete("public:results:standings")
        await cache.invalidate_pattern("public:results:leaderboard:*")
        return await super().after_model_change(data, model, is_created, request)
