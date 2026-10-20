"""Экран «Статистика» — графики и топы."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db.base import async_session_factory
from app.services.admin_statistics import AdminStatisticsService


class StatisticsView(BaseView):
    name = "Статистика"
    icon = "fa-solid fa-chart-simple"

    @expose("/statistics", methods=["GET"])
    async def statistics(self, request: Request) -> Response:
        async with async_session_factory() as session:
            stats = await AdminStatisticsService(session).get_stats()
        top_fans_data = [
            {
                "participant_number": t.participant_number,
                "participant_name": t.participant_name,
                "fans_count": t.fans_count,
            }
            for t in stats.top_fans
        ]
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/statistics.html",
            {"stats": stats, "top_fans_data": top_fans_data},
        )

    @expose("/api/statistics", methods=["GET"])
    async def stats_api(self, request: Request) -> JSONResponse:
        async with async_session_factory() as session:
            stats = await AdminStatisticsService(session).get_stats()
        return JSONResponse(
            {
                "total_fans": stats.total_fans,
                "total_participants": stats.total_participants,
                "total_track_points": stats.total_track_points,
                "top_fans": [
                    {
                        "number": t.participant_number,
                        "name": t.participant_name,
                        "fans_count": t.fans_count,
                    }
                    for t in stats.top_fans
                ],
            }
        )
