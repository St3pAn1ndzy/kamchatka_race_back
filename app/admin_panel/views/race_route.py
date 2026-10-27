"""Экран маршрута этапа и подтверждаемый импорт KML/GPX"""

import secrets

from fastapi import HTTPException
from pydantic import ValidationError
from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db.base import async_session_factory
from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.admin_route import AdminRouteService
from app.services.admin_stage_route import AdminStageRouteService
from app.services.route_upload import read_route_request, read_route_upload


class RaceRouteView(BaseView):
    name = "Гонка и маршрут"
    icon = "fa-solid fa-route"

    @expose("/race-route", methods=["GET"])
    async def race_route(self, request: Request) -> Response:
        token = request.session.setdefault("route_import_csrf", secrets.token_urlsafe(32))
        async with async_session_factory() as session:
            stages = await AdminRouteService(session).get_stages()
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/race_route.html",
            {"stages": stages, "route_import_csrf": token},
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

    @staticmethod
    def _check_import_token(request: Request) -> None:
        """Не разрешает отправлять импорт от имени администратора с чужой страницы"""
        expected = request.session.get("route_import_csrf", "")
        supplied = request.headers.get("X-Route-Import-Token", "")
        if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
            raise HTTPException(403, "Обновите страницу перед импортом маршрута")
        if not 1 <= request.path_params["stage_id"] <= 2147483647:
            raise HTTPException(422, "Некорректный ID этапа")

    @expose("/api/race-route/{stage_id:int}/import/preview", methods=["POST"])
    async def preview_import(self, request: Request) -> JSONResponse:
        """Проверяет файл и этап без изменения сохранённого маршрута"""
        try:
            self._check_import_token(request)
            body = await read_route_upload(request)
            stage_id = request.path_params["stage_id"]
            async with async_session_factory() as session:
                await AdminStageRouteService(session).get_route(stage_id)
            return JSONResponse({"stage_id": stage_id, **body.model_dump(mode="json")})
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @expose("/api/race-route/{stage_id:int}/import/confirm", methods=["POST"])
    async def confirm_import(self, request: Request) -> JSONResponse:
        """Повторно валидирует подтверждение и сохраняет маршрут с аудитом"""
        try:
            self._check_import_token(request)
            body = StageRouteReplaceRequest.model_validate_json(await read_route_request(request))
            stage_id = request.path_params["stage_id"]
            async with async_session_factory() as session:
                points = await AdminStageRouteService(session).replace_route(
                    stage_id, body, admin_id=request.state.admin_id
                )
                return JSONResponse(
                    {
                        "stage_id": stage_id,
                        "points": [
                            {"position": p.position, "lat": p.lat, "lon": p.lon} for p in points
                        ],
                    }
                )
        except ValidationError:
            return JSONResponse({"detail": "Некорректные координаты маршрута"}, status_code=422)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
