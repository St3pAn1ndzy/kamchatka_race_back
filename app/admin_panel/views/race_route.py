"""Экран «Гонка и маршрут» — карта маршрута с этапами."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db.base import async_session_factory
from app.services.admin_route import AdminRouteService


class RaceRouteView(BaseView):
    name = "Гонка и маршрут"
    icon = "fa-solid fa-route"

    @expose("/race-route", methods=["GET"])
    async def race_route(self, request: Request) -> Response:
        async with async_session_factory() as session:
            stages = await AdminRouteService(session).get_stages()
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/race_route.html",
            {"stages": stages},
        )

    @expose("/api/race-route/{stage_id:int}", methods=["GET"])
    async def route_api(self, request: Request) -> JSONResponse:
        """Отдаёт маршрут и КП этапа, указанного в адресе запроса"""
        stage_id = request.path_params["stage_id"]
        async with async_session_factory() as session:
            svc = AdminRouteService(session)
            route = await svc.get_route_by_stage(stage_id)
            checkpoints = await svc.get_checkpoints_by_stage(stage_id)
        return JSONResponse({"route": route, "checkpoints": checkpoints})
