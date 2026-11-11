"""Экран «Контент» — сводка контента."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import Response

from app.db.base import async_session_factory
from app.services.admin_content import AdminContentService


class ContentAdminView(BaseView):
    name = "Контент"
    icon = "fa-solid fa-newspaper"

    @expose("/content", methods=["GET"])
    async def content(self, request: Request) -> Response:
        async with async_session_factory() as session:
            overview = await AdminContentService(session).get_overview()
        return await self.templates.TemplateResponse(
            request,
            "sqladmin/content.html",
            {"overview": overview},
        )
