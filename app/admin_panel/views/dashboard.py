"""Дашборд админ-панели — стартовая страница."""

from dataclasses import asdict

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db.base import async_session_factory
from app.services.admin_dashboard import AdminDashboardService


class DashboardView(BaseView):
    name = "Дашборд"
    icon = "fa-solid fa-gauge-high"

    @expose("/dashboard", methods=["GET"])
    async def dashboard(self, request: Request) -> Response:
        async with async_session_factory() as session:
            service = AdminDashboardService(session)
            stats = await service.get_stats()
            sos_devices = await service.get_sos_devices()

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/dashboard.html",
            {"stats": stats, "sos_devices": sos_devices},
        )

    @expose("/api/dashboard-stats", methods=["GET"])
    async def stats_api(self, request: Request) -> JSONResponse:
        async with async_session_factory() as session:
            service = AdminDashboardService(session)
            stats = await service.get_stats()
            sos_devices = await service.get_sos_devices()

        return JSONResponse(
            {
                "stats": asdict(stats),
                "sos": [
                    {
                        "device_id": d.device_id,
                        "iridium_number": d.iridium_number,
                        "device_name": d.device_name,
                        "participant_id": d.participant_id,
                        "participant_number": d.participant_number,
                        "participant_name": d.participant_name,
                        "stage_number": d.stage_number,
                        "last_message_at": d.last_message_at.isoformat()
                        if d.last_message_at
                        else None,
                        "lat": d.lat,
                        "lon": d.lon,
                    }
                    for d in sos_devices
                ],
            }
        )
