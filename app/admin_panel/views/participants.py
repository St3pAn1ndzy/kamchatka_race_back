from markupsafe import Markup
from sqladmin import action
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from wtforms import FileField, SelectField
from wtforms.validators import NumberRange

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime, fmt_participant_status
from app.admin_panel.utils import get_int_param
from app.db.base import async_session_factory
from app.db.models import AuditLog, Device, Participant
from app.enums import ParticipantStatus
from app.security.admin_sessions import get_active_admin_for_session
from app.services.cache import cache
from app.services.media_storage import media_storage


class UploadImageField(FileField):
    def populate_obj(self, obj, name):
        pass


_LABELS = {
    ParticipantStatus.REGISTERED: "Заявлен",
    ParticipantStatus.ACTIVE: "Активен",
    ParticipantStatus.FINISHED: "Финишировал",
    ParticipantStatus.WITHDRAWN: "Сошёл",
    ParticipantStatus.DISQUALIFIED: "Дисквалифицирован",
}


class DeviceAdmin(BaseAdminView, model=Device):
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
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary text-decoration-none fw-bold">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        Device.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number}</a>"
            )
            if m.stage
            else "—"
        ),
        Device.is_active: lambda m, a: fmt_bool(m.is_active),
        Device.sos_active: lambda m, a: fmt_bool(m.sos_active),
        Device.last_message_at: lambda m, a: fmt_datetime(m.last_message_at),
    }

    column_formatters_detail = {
        Device.participant: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/participant/details/{m.participant.id}" class="text-primary text-decoration-none fw-bold">'
                f"№{m.participant.number} {m.participant.name}</a>"
            )
            if m.participant
            else "—"
        ),
        Device.stage: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/stage/details/{m.stage.id}" class="text-primary text-decoration-none">'
                f"Этап {m.stage.number} — {m.stage.name}</a>"
            )
            if m.stage
            else "—"
        ),
        Device.is_active: lambda m, a: fmt_bool(m.is_active),
        Device.sos_active: lambda m, a: fmt_bool(m.sos_active),
        Device.last_message_at: lambda m, a: fmt_datetime(m.last_message_at),
        Device.track_points: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/track-point/list?device_id={m.id}" class="text-primary text-decoration-none">'
                f"Точек трека: {len(m.track_points)}</a>"
            )
        ],
    }
    column_details_list = [
        Device.iridium_number,
        Device.imei,
        Device.name,
        Device.participant,
        Device.stage,
        Device.is_active,
        Device.battery_percent,
        Device.sos_active,
        Device.last_message_at,
        Device.track_points,
        Device.created_at,
        Device.updated_at,
    ]

    column_default_sort = (Device.iridium_number, False)
    column_searchable_list = [Device.iridium_number, Device.imei]
    column_selectinload = [Device.participant, Device.stage]

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ЧЕРЕЗ list_query ═══
    def list_query(self, request: Request):
        stmt = select(self.model)

        if pid := get_int_param(request, "participant_id"):
            stmt = stmt.where(Device.participant_id == pid)

        if sid := get_int_param(request, "stage_id"):
            stmt = stmt.where(Device.stage_id == sid)

        if q := request.query_params.get("is_active"):
            stmt = stmt.where(Device.is_active.is_(q == "true"))

        if q := request.query_params.get("sos_active"):
            stmt = stmt.where(Device.sos_active.is_(q == "true"))

        return stmt

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

    async def after_model_change(self, data, model, is_created, request) -> None:
        await cache.invalidate_pattern("public:map:*")
        return await super().after_model_change(data, model, is_created, request)

    async def _set_active(self, request, active, action_code):
        pks = await self._parse_pks(request)
        if not pks:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)
        session_id = request.session.get("admin_session_id")
        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            admin_id = admin.id if admin else None
            for pk in pks:
                device = await session.get(Device, pk)
                if device is None:
                    continue
                old_status = device.is_active
                device.is_active = active
                session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action=action_code,
                        entity_type="device",
                        entity_id=str(device.id),
                        payload={"old_status": old_status, "new_status": active},
                    )
                )
            await session.commit()
        await cache.invalidate_pattern("public:map:*")
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)

    @action(
        name="activate",
        label="Активировать",
        confirmation_message="Активировать выбранные трекеры?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_activate(self, request: Request) -> RedirectResponse:
        return await self._set_active(request, True, "device_activated")

    @action(
        name="deactivate",
        label="Деактивировать",
        confirmation_message="Деактивировать выбранные трекеры?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_deactivate(self, request: Request) -> RedirectResponse:
        return await self._set_active(request, False, "device_deactivated")

    @action(
        name="reset-sos",
        label="Сбросить SOS",
        confirmation_message="Сбросить сигнал SOS на выбранных трекерах?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_reset_sos(self, request: Request) -> RedirectResponse:
        pks = await self._parse_pks(request)
        if not pks:
            return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)
        session_id = request.session.get("admin_session_id")
        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            admin_id = admin.id if admin else None
            for pk in pks:
                device = await session.get(Device, pk)
                if device is None:
                    continue
                device.sos_active = False
                session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action="device_sos_reset",
                        entity_type="device",
                        entity_id=str(device.id),
                        payload={"sos_active": False},
                    )
                )
            await session.commit()
        return RedirectResponse(request.url_for("admin:list", identity=self.identity), 302)


class ParticipantAdmin(BaseAdminView, model=Participant):
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
        Participant.number: lambda m, a: Markup(
            f'<a href="/admin-panel/participant/details/{m.id}" class="text-primary fw-bold text-decoration-none">№{m.number}</a>'
        ),
        Participant.discipline_ref: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/discipline/details/{m.discipline_ref.id}" class="text-primary text-decoration-none">'
                f"{m.discipline_ref.name}</a>"
            )
            if m.discipline_ref
            else "—"
        ),
        Participant.status: lambda m, a: fmt_participant_status(m.status),
    }

    column_formatters_detail = {
        Participant.number: lambda m, a: f"№{m.number}",
        Participant.discipline_ref: lambda m, a: (
            Markup(
                f'<a href="/admin-panel/discipline/details/{m.discipline_ref.id}" class="text-primary text-decoration-none">'
                f"{m.discipline_ref.name}</a>"
            )
            if m.discipline_ref
            else "—"
        ),
        Participant.status: lambda m, a: fmt_participant_status(m.status),
        Participant.photo_url: lambda m, a: Markup(
            (
                f'<div class="d-flex align-items-center gap-3">'
                f'<img src="{m.photo_url}" style="width:120px;height:120px;object-fit:cover;border-radius:8px;border:1px solid var(--tblr-border-color);">'
                f'<a href="/admin-panel/participants-card?open={m.id}" target="_blank" class="btn btn-sm btn-primary">'
                f'<i class="fa-regular fa-eye me-1"></i>Открыть в приложении</a>'
                f"</div>"
            )
            if m.photo_url
            else Markup('<span class="text-muted">— фото не загружено</span>')
        ),
        Participant.devices: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/device/list?participant_id={m.id}" class="text-primary text-decoration-none">'
                f"Трекеров: {len(m.devices)}</a>"
            )
        ],
        Participant.official_marks: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/official-mark/list?participant_id={m.id}" class="text-primary text-decoration-none">'
                f"Отметок: {len(m.official_marks)}</a>"
            )
        ],
        Participant.track_points: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/track-point/list?participant_id={m.id}" class="text-primary text-decoration-none">'
                f"Точек трека: {len(m.track_points)}</a>"
            )
        ],
        Participant.fans: lambda m, a: [
            Markup(
                f'<a href="/admin-panel/fan-subscription/list?participant_id={m.id}" class="text-primary text-decoration-none">'
                f"Болельщиков: {len(m.fans)}</a>"
            )
        ],
    }

    column_details_list = [
        Participant.number,
        Participant.name,
        Participant.region,
        Participant.discipline_ref,
        Participant.status,
        Participant.dogs_count,
        Participant.bio,
        Participant.photo_url,
        Participant.devices,
        Participant.official_marks,
        Participant.track_points,
        Participant.fans,
    ]

    column_searchable_list = [Participant.name, Participant.number]
    column_sortable_list = [Participant.number, Participant.name]
    column_selectinload = [Participant.discipline_ref]

    # ═══ РУЧНАЯ ФИЛЬТРАЦИЯ ═══
    def list_query(self, request: Request):
        stmt = select(self.model)
        q = request.query_params

        if status := q.get("status"):
            stmt = stmt.where(Participant.status == status)

        if did := get_int_param(request, "discipline_id"):
            stmt = stmt.where(Participant.discipline_id == did)

        return stmt

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
    }
    form_overrides = {
        "status": SelectField,
        "photo_url": UploadImageField,
    }
    form_args = {
        "dogs_count": {"validators": [NumberRange(min=1, max=20)]},
        "number": {"validators": [NumberRange(min=1)]},
        "status": {"choices": [(s.value, _LABELS[s]) for s in ParticipantStatus]},
    }

    can_export = True
    column_export_list = [
        Participant.number,
        Participant.name,
        Participant.region,
        Participant.status,
        Participant.dogs_count,
    ]

    async def update_model(self, request, pk, data):
        pk_int = int(pk)
        photo = data.get("photo_url")
        if photo is not None and hasattr(photo, "filename"):
            async with async_session_factory() as session:
                p = await session.get(Participant, pk_int)
                data["photo_url"] = p.photo_url if p is not None else None
        return await super().update_model(request, pk_int, data)

    async def create_model(self, request, data):
        photo = data.get("photo_url")
        if photo is not None and hasattr(photo, "filename"):
            data["photo_url"] = None
        return await super().create_model(request, data)

    async def after_model_change(self, data, model, is_created, request) -> None:
        form = await request.form()
        upload = form.get("photo_url")
        if not upload or not hasattr(upload, "filename") or not upload.filename:
            return
        old_url = None
        async with async_session_factory() as session:
            p = await session.get(Participant, model.id)
            if p is not None:
                old_url = p.photo_url
        try:
            new_url = await media_storage.save_image(
                upload, folder="participants", prefix=str(model.number or model.id)
            )
        except ValueError as e:
            print(f"[media] Ошибка загрузки фото участника {model.id}: {e}")
            return
        async with async_session_factory() as session:
            p = await session.get(Participant, model.id)
            if p is None:
                return
            p.photo_url = new_url
            await session.commit()
        if old_url and old_url != new_url and old_url.startswith("/media/"):
            media_storage.delete(old_url)

    async def _set_status(self, request, new_status, action_code):
        raw_pks = request.query_params.getlist("pks")
        pks = [pk.strip() for raw in raw_pks for pk in raw.split(",") if pk.strip()]
        if not pks:
            return RedirectResponse(
                request.url_for("admin:list", identity=self.identity), status_code=302
            )
        session_id = request.session.get("admin_session_id")
        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            admin_id = admin.id if admin else None
            for pk in pks:
                participant = await session.get(Participant, int(pk))
                if participant is None:
                    continue
                old_status = participant.status
                participant.status = new_status
                session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action=action_code,
                        entity_type="participant",
                        entity_id=str(participant.id),
                        payload={"old_status": old_status, "new_status": new_status},
                    )
                )
            await session.commit()
        return RedirectResponse(
            request.url_for("admin:list", identity=self.identity), status_code=302
        )

    @action(
        name="activate",
        label="Активировать",
        confirmation_message="Активировать выбранных участников?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_activate(self, request: Request) -> RedirectResponse:
        return await self._set_status(
            request, ParticipantStatus.ACTIVE.value, "participant_activated"
        )

    @action(
        name="withdraw",
        label="Снять с гонки",
        confirmation_message="Снять выбранных участников с гонки?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_withdraw(self, request: Request) -> RedirectResponse:
        return await self._set_status(
            request, ParticipantStatus.WITHDRAWN.value, "participant_withdrawn"
        )

    @action(
        name="disqualify",
        label="Дисквалифицировать",
        confirmation_message="Дисквалифицировать выбранных участников?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_disqualify(self, request: Request) -> RedirectResponse:
        return await self._set_status(
            request, ParticipantStatus.DISQUALIFIED.value, "participant_disqualified"
        )
