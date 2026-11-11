"""Экран «Результаты» — протоколы этапов."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import Response

from app.db.base import async_session_factory
from app.services.admin_results import AdminResultsService


class ResultsAdminView(BaseView):
    name = "Протоколы этапов"
    icon = "fa-solid fa-medal"

    @expose("/results", methods=["GET"])
    async def results(self, request: Request) -> Response:
        async with async_session_factory() as session:
            stages = await AdminResultsService(session).get_stages()
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/results.html",
            {"stages": stages},
        )
