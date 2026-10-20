from sqladmin import action
from starlette.requests import Request
from starlette.responses import RedirectResponse
from wtforms.validators import NumberRange

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime
from app.db.base import async_session_factory
from app.db.models import AuditLog, OfficialMark, TrackPoint
from app.security.admin_sessions import get_active_admin_for_session
from app.services.cache import cache


class OfficialMarkAdmin(BaseAdminView, model=OfficialMark):
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

    # --- BULK ACTIONS ---

    @action(
        name="cancel-marks",
        label="Отменить отметки",
        confirmation_message="Отменить выбранные отметки? Они будут помечены как отмененные (is_cancelled=True) и не попадут в протокол.",
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
                    continue  # Уже отменена — пропускаем

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

        # Сброс кэша результатов (отметки изменились)
        await cache.invalidate_pattern("public:results:*")

        return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)


class TrackPointAdmin(BaseAdminView, model=TrackPoint):
    name = "Точка трека"
    name_plural = "Точки трека"
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
        TrackPoint.participant: lambda m, a: f"№{m.participant.number}" if m.participant else "—",
        TrackPoint.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        TrackPoint.is_confirmed: lambda m, a: fmt_bool(m.is_confirmed),
    }
    column_default_sort = (TrackPoint.recorded_at, True)
