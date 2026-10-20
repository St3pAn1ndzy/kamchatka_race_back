from sqladmin import action
from starlette.requests import Request
from starlette.responses import RedirectResponse
from wtforms import SelectField
from wtforms.validators import NumberRange

from app.admin_panel.base import BaseAdminView
from app.admin_panel.categories import CategoryAdminEnum
from app.admin_panel.formatters import fmt_bool, fmt_datetime, fmt_participant_status
from app.db.base import async_session_factory
from app.db.models import AuditLog, Device, Participant
from app.enums import ParticipantStatus
from app.security.admin_sessions import get_active_admin_for_session
from app.services.cache import cache

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
            f"№{m.participant.number} {m.participant.name}" if m.participant else "—"
        ),
        Device.stage: lambda m, a: f"Этап {m.stage.number}" if m.stage else "—",
        Device.is_active: lambda m, a: fmt_bool(m.is_active),
        Device.sos_active: lambda m, a: fmt_bool(m.sos_active),
        Device.last_message_at: lambda m, a: fmt_datetime(m.last_message_at),
    }
    column_default_sort = (Device.iridium_number, False)
    column_searchable_list = [Device.iridium_number, Device.imei]

    column_selectinload = [Device.participant, Device.stage]

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

    async def after_model_change(
        self, data: dict, model: Device, is_created: bool, request: Request
    ) -> None:
        """Инвалидация кэша карты после изменения трекера."""
        await cache.invalidate_pattern("public:map:*")
        return await super().after_model_change(data, model, is_created, request)

    # --- BULK ACTIONS ---

    async def _set_active(
        self, request: Request, active: bool, action_code: str
    ) -> RedirectResponse:
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

        # Инвалидация кэша карты — изменилось состояние трекеров
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
        confirmation_message="Деактивировать выбранные трекеры? (Данные с них перестанут учитываться)",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_deactivate(self, request: Request) -> RedirectResponse:
        return await self._set_active(request, False, "device_deactivated")

    @action(
        name="reset-sos",
        label="Сбросить SOS",
        confirmation_message="Сбросить сигнал SOS на выбранных трекерах? Убедитесь, что ситуация действительно решена!",
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
        Participant.discipline_ref: lambda m, a: m.discipline_ref.name if m.discipline_ref else "—",
        Participant.status: lambda m, a: fmt_participant_status(m.status),
    }
    column_searchable_list = [Participant.name, Participant.number]
    column_sortable_list = [Participant.number, Participant.name]

    column_selectinload = [Participant.discipline_ref]

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

    can_export = True

    column_export_list = [
        Participant.number,
        Participant.name,
        Participant.region,
        Participant.status,
        Participant.dogs_count,
    ]

    # --- BULK ACTIONS ---

    async def _set_status(
        self, request: Request, new_status: str, action_code: str
    ) -> RedirectResponse:

        raw_pks = request.query_params.getlist("pks")
        pks = [pk.strip() for raw in raw_pks for pk in raw.split(",") if pk.strip()]

        if not pks:
            return RedirectResponse(
                request.url_for("admin:list", identity=self.identity),
                status_code=302,
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
            request.url_for("admin:list", identity=self.identity),
            status_code=302,
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
        confirmation_message="Дисквалифицировать выбранных участников? Это действие нельзя отменить одной кнопкой.",
        add_in_list=True,
        add_in_detail=True,
    )
    async def action_disqualify(self, request: Request) -> RedirectResponse:
        return await self._set_status(
            request, ParticipantStatus.DISQUALIFIED.value, "participant_disqualified"
        )
