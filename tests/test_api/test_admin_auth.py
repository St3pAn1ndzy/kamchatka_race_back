from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.admin.auth import login_admin
from app.schemas.admin import AdminLoginRequest


async def test_admin_login_rejects_bad_credentials():
    """Неверные данные дают 401 без создания сессии и коммита"""
    session = AsyncMock()
    with (
        patch(
            "app.api.admin.auth.authenticate_admin_by_password", new_callable=AsyncMock
        ) as authenticate,
        patch("app.api.admin.auth.create_admin_session", new_callable=AsyncMock) as create_session,
    ):
        authenticate.return_value = None
        with pytest.raises(HTTPException) as exc:
            await login_admin(AdminLoginRequest(login="admin", password="bad"), session)
    assert exc.value.status_code == 401
    create_session.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_admin_login_commits_session_before_issuing_token():
    """Токен создаётся только после сохранения серверной сессии"""
    session = AsyncMock()
    admin = SimpleNamespace(id=3)
    stored_session = SimpleNamespace(session_id="session-1")
    committed = False

    async def commit():
        nonlocal committed
        committed = True

    def issue_token(*_args):
        assert committed
        return "jwt", 3600

    session.commit.side_effect = commit
    with (
        patch(
            "app.api.admin.auth.authenticate_admin_by_password", new_callable=AsyncMock
        ) as authenticate,
        patch("app.api.admin.auth.create_admin_session", new_callable=AsyncMock) as create_session,
        patch("app.api.admin.auth.create_admin_token", side_effect=issue_token) as token,
    ):
        authenticate.return_value = admin
        create_session.return_value = stored_session
        response = await login_admin(AdminLoginRequest(login="admin", password="secret"), session)
    assert response.access_token == "jwt"
    authenticate.assert_awaited_once_with(session, "admin", "secret")
    create_session.assert_awaited_once_with(session, admin, surface="api")
    session.commit.assert_awaited_once()
    token.assert_called_once_with(3, "session-1")
