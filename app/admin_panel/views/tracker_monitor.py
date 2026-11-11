"""Кастомный экран: Мониторинг трекеров."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import Response

from app.db.base import async_session_factory
from app.services.admin_tracker import AdminTrackerService


class TrackerMonitorView(BaseView):
    name = "Мониторинг трекеров"
    icon = "fa-solid fa-satellite-dish"

    @expose("/tracker-monitor", methods=["GET"])
    async def tracker_monitor(self, request: Request) -> Response:
        async with async_session_factory() as session:
            trackers = await AdminTrackerService(session).get_trackers()

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/tracker_monitor.html",
            {"trackers": trackers},
        )
