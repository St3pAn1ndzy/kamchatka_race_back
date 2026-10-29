"""Views для сущностей события: сезоны, дисциплины, этапы, КП."""

from markupsafe import Markup, escape
from sqlalchemy import select
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
from app.admin_panel.utils import get_int_param
from app.db.models import Checkpoint, Discipline, Season, Stage, StageRoutePoint
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
        Checkpoint.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none fw-bold">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        Checkpoint.code: lambda m, a: Markup(
            f'<a href="/admin-panel/checkpoint/details/{m.id}" class="text-primary text-decoration-none fw-bold">{m.code}</a>'
        ),
        Checkpoint.has_judge: lambda m, a: fmt_bool(m.has_judge),
        Checkpoint.is_public: lambda m, a: fmt_bool(m.is_public),
        Checkpoint.kind: lambda m, a: fmt_checkpoint_kind(m.kind),
    }
    column_formatters_detail = {
        Checkpoint.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none fw-bold">'
                f"Этап {m.stage.number} — {m.stage.name}</a>"
            )
            if m.stage
            else "—"
        ),
        Checkpoint.has_judge: lambda m, a: fmt_bool(m.has_judge),
        Checkpoint.is_public: lambda m, a: fmt_bool(m.is_public),
        Checkpoint.kind: lambda m, a: fmt_checkpoint_kind(m.kind),
        Checkpoint.lat: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=12&l=map" target="_blank" class="text-primary text-decoration-none">'
                f'{m.lat:.5f} <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.lat is not None
            else "—"
        ),
        Checkpoint.lon: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=12&l=map" target="_blank" class="text-primary text-decoration-none">'
                f'{m.lon:.5f} <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.lon is not None
            else "—"
        ),
        Checkpoint.official_marks: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/official-mark/list?checkpoint_id={m.id}" class="text-primary text-decoration-none">'
                f"Отметок: {len(m.official_marks)}</a>"
            )
        ],
    }
    column_details_list = [
        Checkpoint.stage,
        Checkpoint.code,
        Checkpoint.name,
        Checkpoint.kind,
        Checkpoint.description,
        Checkpoint.km_from_race_start,
        Checkpoint.lat,
        Checkpoint.lon,
        Checkpoint.altitude,
        Checkpoint.has_judge,
        Checkpoint.is_public,
        Checkpoint.official_marks,
    ]
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

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(Checkpoint.stage_id == sid)

        if kind := q.get("kind"):
            stmt = stmt.where(Checkpoint.kind == kind)

        if q.get("is_public") == "true":
            stmt = stmt.where(Checkpoint.is_public.is_(True))
        elif q.get("is_public") == "false":
            stmt = stmt.where(Checkpoint.is_public.is_(False))

        return stmt


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
        Discipline.season: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/season/details/{m.season.id}" class="text-primary text-decoration-none">'
                f"{m.season.title}</a>"
            )
            if m.season
            else "—"
        ),
    }
    column_formatters_detail = {
        Discipline.is_active: lambda m, a: fmt_bool(m.is_active),
        Discipline.season: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/season/details/{m.season.id}" class="text-primary text-decoration-none">'
                f"{m.season.title}</a>"
            )
            if m.season
            else "—"
        ),
    }
    column_details_list = [
        Discipline.id,
        Discipline.season,
        Discipline.code,
        Discipline.name,
        Discipline.sort_order,
        Discipline.is_active,
    ]
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
    column_formatters_detail = {
        Season.is_active: lambda m, a: fmt_bool(m.is_active),
        Season.starts_at: lambda m, a: fmt_datetime(m.starts_at),
        Season.ends_at: lambda m, a: fmt_datetime(m.ends_at),
    }
    column_details_list = [
        Season.id,
        Season.year,
        Season.title,
        Season.starts_at,
        Season.ends_at,
        Season.is_active,
    ]
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
        Stage.number: lambda m, a: Markup(
            f'<a href="/admin-panel/stage/details/{m.id}" class="text-primary fw-bold text-decoration-none">{m.number}</a>'
        ),
        Stage.season: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/season/details/{m.season.id}" class="text-primary text-decoration-none">'
                f"{m.season.title}</a>"
            )
            if m.season
            else "—"
        ),
        Stage.start_time: lambda m, a: fmt_datetime(m.start_time),
        Stage.status: lambda m, a: fmt_stage_status(m.status),
        Stage.results_publication: lambda m, a: fmt_publication(m.results_publication),
        Stage.name: lambda m, a: Markup(
            f'{escape(m.name)} <a href="/admin-panel/race-route?stage_id={m.id}#importTitle" '
            'class="btn btn-sm btn-outline-primary">Заменить маршрут</a>'
        ),
    }
    column_formatters_detail = {
        Stage.number: lambda m, a: f"№{m.number}",
        Stage.season: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/season/details/{m.season.id}" class="text-primary text-decoration-none fw-bold">'
                f"{m.season.title}</a>"
            )
            if m.season
            else "—"
        ),
        Stage.start_time: lambda m, a: fmt_datetime(m.start_time),
        Stage.finish_time: lambda m, a: fmt_datetime(m.finish_time),
        Stage.status: lambda m, a: fmt_stage_status(m.status),
        Stage.results_publication: lambda m, a: fmt_publication(m.results_publication),
        Stage.checkpoints: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/checkpoint/list?stage_id={m.id}" class="text-primary text-decoration-none">'
                f"КП: {len(m.checkpoints)}</a>"
            )
        ],
        Stage.route_points: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/stage-route-point/list?stage_id={m.id}" '
                f'class="text-primary text-decoration-none">'
                f"Точек маршрута: {len(m.route_points)}</a>"
            )
        ],
    }
    column_details_list = [
        Stage.number,
        Stage.name,
        Stage.season,
        Stage.distance_km,
        Stage.start_time,
        Stage.finish_time,
        Stage.tracker_interval_seconds,
        Stage.status,
        Stage.results_publication,
        Stage.checkpoints,
        Stage.route_points,
    ]
    column_searchable_list = [Stage.name]
    column_sortable_list = [Stage.order_index, Stage.number, Stage.start_time]
    column_selectinload = [Stage.season, Stage.checkpoints, Stage.route_points]

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

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if sid := get_int_param(request, "season_id"):
            stmt = stmt.where(Stage.season_id == sid)

        if status := q.get("status"):
            stmt = stmt.where(Stage.status == status)

        if pub := q.get("results_publication"):
            stmt = stmt.where(Stage.results_publication == pub)

        return stmt

    async def after_model_change(
        self, data: dict, model: Stage, is_created: bool, request: Request
    ) -> None:
        await cache.invalidate_pattern("public:stages:*")
        await cache.invalidate_pattern("public:disciplines:*")
        await cache.invalidate_pattern(f"public:map:model:{model.id}:*")
        await cache.delete(f"public:map:checkpoint:{model.id}")
        await cache.invalidate_pattern(f"public:map:track:{model.id}:*")
        await cache.delete(f"public:results:stage:{model.id}")
        await cache.delete("public:results:standings")
        await cache.invalidate_pattern("public:results:leaderboard:*")
        return await super().after_model_change(data, model, is_created, request)


class StageRoutePointAdmin(BaseAdminView, model=StageRoutePoint):
    name = "Точка маршрута"
    name_plural = "Точки маршрута"
    identity = "stage-route-point"
    icon = "fa-solid fa-route"
    category = CategoryAdminEnum.CATEGORY_EVENT
    category_icon = "fa-solid fa-calendar-days"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        StageRoutePoint.stage,
        StageRoutePoint.position,
        StageRoutePoint.lat,
        StageRoutePoint.lon,
    ]
    column_labels = {
        StageRoutePoint.stage: "Этап",
        StageRoutePoint.position: "Позиция",
        StageRoutePoint.lat: "Широта",
        StageRoutePoint.lon: "Долгота",
    }
    column_formatters = {
        StageRoutePoint.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
    }
    column_details_list = [
        StageRoutePoint.stage,
        StageRoutePoint.position,
        StageRoutePoint.lat,
        StageRoutePoint.lon,
    ]
    column_default_sort = (StageRoutePoint.stage_id, False)
    column_selectinload = [StageRoutePoint.stage]

    def list_query(self, request: Request):
        stmt = select(self.model)
        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(StageRoutePoint.stage_id == sid)
        return stmt
