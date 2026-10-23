"""Экран «Участники» — превью карточек."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db.base import async_session_factory
from app.services.admin_participant import AdminParticipantService


class ParticipantCardView(BaseView):
    name = "Участники"
    icon = "fa-solid fa-people-group"

    @expose("/participants-card", methods=["GET"])
    async def participants_card(self, request: Request) -> Response:
        async with async_session_factory() as session:
            participants = await AdminParticipantService(session).get_all_participants()
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/participant_card.html",
            {"participants": participants},
        )

    @expose("/api/participant-card/{participant_id:int}", methods=["GET"])
    async def participant_api(self, request: Request) -> JSONResponse:
        """Отдаёт карточку участника по числовому параметру URL"""
        participant_id = request.path_params["participant_id"]
        async with async_session_factory() as session:
            p = await AdminParticipantService(session).get_participant_detail(participant_id)
        if not p:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(
            {
                "id": p.id,
                "number": p.number,
                "name": p.name,
                "region": p.region,
                "photo_url": p.photo_url,
                "bio": p.bio,
                "dogs_count": p.dogs_count,
                "status": p.status,
                "discipline_name": p.discipline_name,
                "fans_count": p.fans_count,
                "device_status": p.device_status,
            }
        )
