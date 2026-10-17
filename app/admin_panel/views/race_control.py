"""Кастомный экран: Оперативный штаб гонки (Race Control)."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import Response

from app.db.base import async_session_factory
from app.services.admin_race_control import AdminRaceControlService


class RaceControlView(BaseView):
    name = "Оперативный штаб"
    icon = "fa-solid fa-tower-broadcast"

    @expose("/race-control", methods=["GET"])
    async def race_control(self, request: Request) -> Response:
        async with async_session_factory() as session:
            states = await AdminRaceControlService(session).get_race_states()

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/race_control.html",
            {"states": states},  # передаем список
        )
