"""Кастомный экран: Отправка Push-уведомлений."""

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.db.base import async_session_factory
from app.services.admin_notifications import AdminNotificationService


class PushSenderView(BaseView):
    name = "Рассылка Push"
    icon = "fa-solid fa-bullhorn"

    @expose("/push-sender", methods=["GET"])
    async def push_sender(self, request: Request) -> Response:
        """Показываем форму."""
        async with async_session_factory() as session:
            participants = await AdminNotificationService(session).get_participants()

        # Если в URL есть ?success=10, значит только что отправили 10 сообщений
        success_count = request.query_params.get("success")

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/push_sender.html",
            {"participants": participants, "success_count": success_count},
        )

    @expose("/push-sender", methods=["POST"])
    async def push_sender_post(self, request: Request) -> Response:
        """Обрабатываем отправку формы."""
        form = await request.form()
        title = str(form.get("title", "")).strip()
        body = str(form.get("body", "")).strip()
        target_raw = form.get("target")

        # Превращаем строку в ID или None
        target_id = int(target_raw) if target_raw and target_raw != "all" else None

        if not title or not body:
            return RedirectResponse("/admin-panel/push-sender?error=empty", status_code=302)

        async with async_session_factory() as session:
            count = await AdminNotificationService(session).send_broadcast(title, body, target_id)

        return RedirectResponse(f"/admin-panel/push-sender?success={count}", status_code=302)
