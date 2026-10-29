from fastapi import HTTPException
from markupsafe import Markup
from sqladmin import action
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from wtforms.validators import NumberRange

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.admin_panel.utils import get_int_param
from app.db.base import async_session_factory
from app.db.models import AuditLog, OfficialMark, TrackPoint
from app.schemas.admin_marks import OfficialMarkCreateRequest
from app.security.admin_sessions import get_active_admin_for_session
from app.services.admin_marks import AdminMarkService
from app.services.cache import cache


class OfficialMarkAdmin(BaseAdminView, model=OfficialMark):
    name = "Отметка"
    name_plural = "Отметки"
    identity = "official-mark"
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
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary text-decoration-none fw-bold">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        OfficialMark.checkpoint: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/checkpoint/details/{m.checkpoint.id}" class="text-primary text-decoration-none">'
                f"{m.checkpoint.code} — {m.checkpoint.name}</a>"
            )
            if m.checkpoint
            else "—"
        ),
        OfficialMark.is_cancelled: lambda m, a: fmt_bool(m.is_cancelled),
        OfficialMark.entered_by: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/admin-account/details/{m.entered_by.id}" class="text-primary text-decoration-none">'
                f"{m.entered_by.login}</a>"
            )
            if m.entered_by
            else "—"
        ),
        OfficialMark.penalty_minutes: lambda m, a: (
            Markup(f'<span class="text-danger fw-bold">+{m.penalty_minutes}</span>')
            if m.penalty_minutes and m.penalty_minutes > 0
            else Markup('<span class="text-muted">—</span>')
        ),
        OfficialMark.mandatory_stop_minutes: lambda m, a: (
            Markup(f'<span class="text-warning fw-bold">{m.mandatory_stop_minutes}</span>')
            if m.mandatory_stop_minutes and m.mandatory_stop_minutes > 0
            else Markup('<span class="text-muted">—</span>')
        ),
    }
    column_formatters_detail = {
        OfficialMark.mark_time: lambda m, a: fmt_datetime(m.mark_time),
        OfficialMark.participant: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary text-decoration-none fw-bold">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        OfficialMark.checkpoint: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/checkpoint/details/{m.checkpoint.id}" class="text-primary text-decoration-none">'
                f"{m.checkpoint.code} — {m.checkpoint.name}</a>"
            )
            if m.checkpoint
            else "—"
        ),
        OfficialMark.is_cancelled: lambda m, a: fmt_bool(m.is_cancelled),
        OfficialMark.entered_by: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/admin-account/details/{m.entered_by.id}" class="text-primary text-decoration-none">'
                f"{m.entered_by.login}</a>"
            )
            if m.entered_by
            else "—"
        ),
        OfficialMark.cancels_mark: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/official-mark/details/{m.cancels_mark.id}" class="text-primary text-decoration-none">'
                f"Отметка #{m.cancels_mark.id}</a>"
            )
            if m.cancels_mark
            else "—"
        ),
        OfficialMark.created_at: lambda m, a: fmt_datetime(m.created_at),
    }
    column_details_list = [
        OfficialMark.mark_time,
        OfficialMark.participant,
        OfficialMark.checkpoint,
        OfficialMark.penalty_minutes,
        OfficialMark.mandatory_stop_minutes,
        OfficialMark.comment,
        OfficialMark.is_cancelled,
        OfficialMark.cancel_reason,
        OfficialMark.cancels_mark,
        OfficialMark.entered_by,
        OfficialMark.created_at,
    ]
    column_default_sort = (OfficialMark.mark_time, True)
    column_searchable_list = [OfficialMark.comment]
    can_edit = False
    column_selectinload = [
        OfficialMark.participant,
        OfficialMark.checkpoint,
        OfficialMark.entered_by,
    ]

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
    can_export = True
    column_export_list = [
        OfficialMark.mark_time,
        OfficialMark.participant,
        OfficialMark.checkpoint,
        OfficialMark.penalty_minutes,
        OfficialMark.mandatory_stop_minutes,
    ]

    async def insert_model(self, request: Request, data: dict):
        admin_id = getattr(request.state, "admin_id", None)
        if admin_id is None:
            raise ValueError("Не удалось определить администратора")
        body = OfficialMarkCreateRequest(
            participant_id=data["participant"],
            checkpoint_id=data["checkpoint"],
            mark_time=data["mark_time"],
            penalty_minutes=data["penalty_minutes"],
            mandatory_stop_minutes=data["mandatory_stop_minutes"],
            comment=data.get("comment"),
        )
        # Панель использует синхронную сессию, а сервис отметок — асинхронную
        async with async_session_factory() as session:
            try:
                return await AdminMarkService(session).create(body, admin_id=admin_id)
            except HTTPException as exc:
                raise ValueError(exc.detail) from exc

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if pid := get_int_param(request, "participant_id"):
            stmt = stmt.where(OfficialMark.participant_id == pid)

        if cid := get_int_param(request, "checkpoint_id"):
            stmt = stmt.where(OfficialMark.checkpoint_id == cid)

        if aid := get_int_param(request, "entered_by_admin_id"):
            stmt = stmt.where(OfficialMark.entered_by_admin_id == aid)

        if q.get("is_cancelled") == "true":
            stmt = stmt.where(OfficialMark.is_cancelled.is_(True))
        elif q.get("is_cancelled") == "false":
            stmt = stmt.where(OfficialMark.is_cancelled.is_(False))

        return stmt

    @action(
        name="cancel-marks",
        label="Отменить отметки",
        confirmation_message="Отменить выбранные отметки?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_cancel_marks(self, request: Request) -> RedirectResponse:
        pks = await self._parse_pks(request)
        if not pks:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)

        session_id = request.session.get("admin_session_id")
        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            admin_id = admin.id if admin else None

            for pk in pks:
                mark = await session.get(OfficialMark, pk)
                if mark is None or mark.is_cancelled:
                    continue
                mark.is_cancelled = True
                mark.cancel_reason = f"Отменено администратором ({admin.display_name if admin else 'Admin'}) через панель"
                session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action="official_mark_cancelled",
                        entity_type="official_mark",
                        entity_id=str(mark.id),
                        payload={"is_cancelled": True, "reason": mark.cancel_reason},
                    )
                )
            await session.commit()

        await cache.invalidate_pattern("public:results:*")
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)


class TrackPointAdmin(BaseAdminView, model=TrackPoint):
    name = "Точка трека"
    name_plural = "Точки трека"
    identity = "track-point"
    icon = "fa-solid fa-location-dot"
    category = CategoryAdminEnum.CATEGORY_RESULTS
    category_icon = "fa-solid fa-trophy"

    can_create = False
    can_edit = False

    column_selectinload = [TrackPoint.participant, TrackPoint.stage]

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
        TrackPoint.participant: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary text-decoration-none fw-bold">'
                f"№{m.participant.number}</a>"
            )
            if m.participant
            else "—"
        ),
        TrackPoint.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        TrackPoint.is_confirmed: lambda m, a: fmt_bool(m.is_confirmed),
        TrackPoint.lat: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=14&l=map" target="_blank" class="text-primary text-decoration-none">'
                f"{m.lat:.5f}</a>"
            )
            if m.lat is not None
            else "—"
        ),
        TrackPoint.lon: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=14&l=map" target="_blank" class="text-primary text-decoration-none">'
                f"{m.lon:.5f}</a>"
            )
            if m.lon is not None
            else "—"
        ),
    }
    column_formatters_detail = {
        TrackPoint.recorded_at: lambda m, a: fmt_datetime(m.recorded_at),
        TrackPoint.participant: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary text-decoration-none fw-bold">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        TrackPoint.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        TrackPoint.is_confirmed: lambda m, a: fmt_bool(m.is_confirmed),
        TrackPoint.lat: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=14&l=map" target="_blank" class="text-primary text-decoration-none">'
                f'{m.lat:.5f} <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.lat is not None
            else "—"
        ),
        TrackPoint.lon: lambda m, a: (
            Markup(
                f'<a href="https://yandex.ru/maps/?pt={m.lon},{m.lat}&z=14&l=map" target="_blank" class="text-primary text-decoration-none">'
                f'{m.lon:.5f} <i class="fa-solid fa-arrow-up-right-from-square ms-1 small"></i></a>'
            )
            if m.lon is not None
            else "—"
        ),
    }
    column_details_list = [
        TrackPoint.recorded_at,
        TrackPoint.participant,
        TrackPoint.stage,
        TrackPoint.lat,
        TrackPoint.lon,
        TrackPoint.km_from_start,
        TrackPoint.average_speed_kmh,
        TrackPoint.is_confirmed,
        TrackPoint.device_id,
    ]
    column_default_sort = (TrackPoint.recorded_at, True)

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if pid := get_int_param(request, "participant_id"):
            stmt = stmt.where(TrackPoint.participant_id == pid)

        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(TrackPoint.stage_id == sid)

        if did := get_int_param(request, "device_id"):
            stmt = stmt.where(TrackPoint.device_id == did)

        if q.get("is_confirmed") == "true":
            stmt = stmt.where(TrackPoint.is_confirmed.is_(True))
        elif q.get("is_confirmed") == "false":
            stmt = stmt.where(TrackPoint.is_confirmed.is_(False))

        return stmt
