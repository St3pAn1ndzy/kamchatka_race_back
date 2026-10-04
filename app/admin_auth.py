"""Авторизация для встроенной SQLAdmin-панели"""

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.db.base import async_session_factory
from app.security.admin_sessions import (
    authenticate_admin_by_password,
    create_admin_session,
    get_active_admin_for_session,
    revoke_admin_session,
)


class AdminPanelAuth(AuthenticationBackend):
    """Проверяет SQLAdmin через серверные admin-сессии"""

    async def login(self, request: Request) -> bool:
        """Обрабатываем форму входа SQLAdmin"""
        form = await request.form()
        login = str(form.get("username", ""))
        password = str(form.get("password", ""))

        async with async_session_factory() as session:
            admin = await authenticate_admin_by_password(session, login, password)
            if admin is None:
                return False

            admin_session = await create_admin_session(session, admin, surface="sqladmin")
            await session.commit()

            request.session["admin_session_id"] = admin_session.session_id
            return True

    async def logout(self, request: Request) -> bool:
        """Отзываем SQLAdmin-сессию и чистим cookie"""
        session_id = request.session.get("admin_session_id")
        if session_id:
            async with async_session_factory() as session:
                await revoke_admin_session(session, str(session_id), surface="sqladmin")
                await session.commit()

        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Проверяем SQLAdmin-сессию при каждом запросе"""
        session_id = request.session.get("admin_session_id")
        if not session_id:
            return False

        async with async_session_factory() as session:
            admin = await get_active_admin_for_session(session, str(session_id))
            return admin is not None
