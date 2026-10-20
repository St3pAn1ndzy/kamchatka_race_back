"""Экран импорта протоколов из CSV."""

import logging

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.db.base import async_session_factory
from app.db.models.stage import Stage
from app.security.admin_sessions import get_active_admin_for_session
from app.services.admin_marks import AdminMarkService

logger = logging.getLogger("avacha.admin")


class MarkImportView(BaseView):
    name = "Импорт протоколов (CSV)"
    icon = "fa-solid fa-file-csv"

    @expose("/mark-import", methods=["GET"])
    async def import_form(self, request: Request) -> Response:
        """Показываем форму загрузки."""
        async with async_session_factory() as session:
            # Получаем список этапов для выпадающего списка
            from sqlalchemy import select

            stages = (await session.execute(select(Stage).order_by(Stage.number))).scalars().all()

        return await self.templates.TemplateResponse(
            request, "sqladmin/mark_import.html", {"stages": stages}
        )

    @expose("/mark-import", methods=["POST"])
    async def import_post(self, request: Request) -> Response:
        """Обрабатываем загруженный файл."""
        form = await request.form()
        file = form.get("file")
        stage_id_str = form.get("stage_id")

        if not file or not stage_id_str:
            return RedirectResponse(
                "/admin-panel/mark-import?error=missing_fields", status_code=302
            )

        stage_id = int(stage_id_str)
        file_content = await file.read()

        # Получаем ID админа из сессии
        session_id = request.session.get("admin_session_id")
        admin_id = None
        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id or ""))
            if admin:
                admin_id = admin.id

            # Запускаем импорт
            try:
                service = AdminMarkService(session)
                count = await service.import_from_csv(file_content, stage_id, admin_id or 1)
                return RedirectResponse(
                    f"/admin-panel/mark-import?success={count}", status_code=302
                )
            except Exception as e:
                logger.error(f"Ошибка импорта CSV: {e}", exc_info=True)
                return RedirectResponse(
                    "/admin-panel/mark-import?error=import_failed", status_code=302
                )
