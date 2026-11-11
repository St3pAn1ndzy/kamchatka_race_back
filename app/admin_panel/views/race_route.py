"""Экран маршрута этапа и подтверждаемый импорт KML/GPX"""

import hashlib
import math
import secrets

from fastapi import HTTPException
from pydantic import ValidationError
from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.admin_panel.utils import get_int_param
from app.db.base import async_session_factory
from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.admin_route import AdminRouteService
from app.services.admin_stage_route import AdminStageRouteService
from app.services.race_route_file import parse_race_route_file
from app.services.race_route_import import RaceRouteImportService
from app.services.race_route_upload import read_race_upload
from app.services.route_file import RouteFileError
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
            {
                "stages": stages,
                "route_import_csrf": token,
                "selected_stage_id": get_int_param(request, "stage_id"),
            },
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
        if not 1 <= request.path_params.get("stage_id", 1) <= 2147483647:
            raise HTTPException(422, "Некорректный ID этапа")

    @expose("/api/race-route/import/preview", methods=["POST"])
    async def preview_race(self, request: Request) -> JSONResponse:
        """Разбирает все линии без записи, уменьшая только изображение предпросмотра"""
        try:
            self._check_import_token(request)
            content, filename, _ = await read_race_upload(request)
            lines = parse_race_route_file(content, filename)
            for line in lines:
                original = line["points"]
                line["point_count"] = len(original)
                step = max(1, math.ceil(len(original) / 800))
                line["points"] = original[::step]
                if line["points"][-1] != original[-1]:
                    line["points"].append(original[-1])
            return JSONResponse({"lines": lines})
        except RouteFileError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @expose("/api/race-route/import/confirm", methods=["POST"])
    async def confirm_race(self, request: Request) -> JSONResponse:
        """Повторно читает исходный файл и атомарно сохраняет выбранные этапы и КП"""
        try:
            self._check_import_token(request)
            content, filename, mapping = await read_race_upload(request)
            lines = parse_race_route_file(content, filename)
            async with async_session_factory() as session:
                ids = await RaceRouteImportService(session).save(
                    lines,
                    mapping,
                    admin_id=request.state.admin_id,
                    file_hash=hashlib.sha256(content).hexdigest(),
                )
            return JSONResponse({"stage_ids": ids})
        except (ValidationError, RouteFileError) as exc:
            detail = str(exc) if isinstance(exc, RouteFileError) else "Некорректное сопоставление"
            return JSONResponse({"detail": detail}, status_code=422)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

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
