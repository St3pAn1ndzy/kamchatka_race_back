"""Авторизация для встроенной SQLAdmin-панели"""

from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from app.db.base import async_session_factory
from app.db.models.admin_account import AdminAccount
from app.security.passwords import verify_password


class AdminPanelAuth(AuthenticationBackend):
    """Проверяет логин админа и хранит id админа в подписанной cookie-сессии"""

    async def login(self, request: Request) -> bool:
        """Обрабатываем форму входа SQLAdmin"""
        form = await request.form()
        login = str(form.get("username", ""))
        password = str(form.get("password", ""))

        async with async_session_factory() as session:
            admin = (
                await session.execute(select(AdminAccount).where(AdminAccount.login == login))
            ).scalar_one_or_none()

            if admin is None:
                return False
            if not admin.is_active:
                return False
            if not admin.password_hash:
                return False
            if not verify_password(password, admin.password_hash):
                return False

            # В cookie кладём только id, сама cookie подписана SessionMiddleware
            request.session["admin_id"] = admin.id
            return True

    async def logout(self, request: Request) -> bool:
        """Очистить cookie-сессию SQLAdmin"""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Проверяем доступ при каждом запросе к SQLAdmin"""
        admin_id = request.session.get("admin_id")
        if admin_id is None:
            return False

        try:
            admin_id_int = int(admin_id)
        except (TypeError, ValueError):
            return False

        async with async_session_factory() as session:
            admin = await session.get(AdminAccount, admin_id_int)
            return admin is not None and admin.is_active
