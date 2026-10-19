from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.auth import accept_consent, auth_vk, delete_me, me
from app.db.models.user import User
from app.schemas.public import ConsentIn, VKAuthRequest


def _user() -> User:
    return User(
        id=7,
        vk_user_id=101,
        first_name="Test",
        last_name="User",
        notifications_allowed=True,
        is_favorite_app=False,
    )


@pytest.mark.parametrize("params", [{}, {"vk_user_id": "bad"}])
async def test_vk_login_rejects_invalid_signature(params):
    """Некорректная подпись даёт 401 до обращения к репозиторию и БД"""
    users = AsyncMock()
    session = AsyncMock()
    with (
        patch("app.api.v1.auth.verify_vk_launch_params", return_value=False),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_vk(VKAuthRequest(params=params), users, session)
    assert exc.value.status_code == 401
    users.get_by_vk_user_id.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_vk_login_requires_numeric_user_id_after_valid_signature():
    """После проверки подписи нечисловой ID пользователя даёт 400"""
    with (
        patch("app.api.v1.auth.verify_vk_launch_params", return_value=True),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_vk(VKAuthRequest(params={"vk_user_id": "bad"}), AsyncMock(), AsyncMock())
    assert exc.value.status_code == 400


async def test_vk_login_creates_user_and_commits_before_token():
    """Новый пользователь сохраняется, а токен выдаётся после коммита"""
    users = AsyncMock()
    users.get_by_vk_user_id.return_value = None
    users.create.return_value = _user()
    session = AsyncMock()
    committed = False

    async def commit():
        nonlocal committed
        committed = True

    def issue_token(*_args):
        assert committed
        return "token", 3600

    session.commit.side_effect = commit
    with (
        patch("app.api.v1.auth.verify_vk_launch_params", return_value=True),
        patch("app.api.v1.auth.create_user_token", side_effect=issue_token) as token,
    ):
        response = await auth_vk(
            VKAuthRequest(
                params={"vk_user_id": "101", "vk_are_notifications_enabled": "1"},
                user_info={"first_name": "Test", "last_name": "User"},
            ),
            users,
            session,
        )
    assert response.is_new_user is True
    assert response.access_token == "token"
    users.create.assert_awaited_once_with(
        vk_user_id=101,
        first_name="Test",
        last_name="User",
        photo_url=None,
        platform=None,
        notifications_allowed=True,
    )
    session.commit.assert_awaited_once()
    token.assert_called_once_with(7, 101)


async def test_vk_login_updates_existing_user():
    """Повторный вход обновляет профиль и активность без создания дубля"""
    users = AsyncMock()
    users.get_by_vk_user_id.return_value = _user()
    users.update_from_vk.return_value = _user()
    with (
        patch("app.api.v1.auth.verify_vk_launch_params", return_value=True),
        patch("app.api.v1.auth.create_user_token", return_value=("token", 3600)),
    ):
        response = await auth_vk(VKAuthRequest(params={"vk_user_id": "101"}), users, AsyncMock())
    assert response.is_new_user is False
    users.create.assert_not_awaited()
    users.update_from_vk.assert_awaited_once()
    users.touch_last_seen.assert_awaited_once()


async def test_me_requires_consent_until_accepted():
    """Профиль требует согласия до принятия актуальной версии политики"""
    user = _user()
    assert (await me(user)).consent_required is True
    user.consent_version = "1.0"
    from datetime import UTC, datetime

    user.consent_accepted_at = datetime.now(UTC)
    assert (await me(user)).consent_required is False


async def test_consent_revocation_anonymizes_and_commits():
    """Отзыв согласия запускает анонимизацию и сохраняет изменения"""
    user = _user()
    session = AsyncMock()
    with patch("app.api.v1.auth.anonymize_user", new_callable=AsyncMock) as anonymize:
        response = await accept_consent(
            ConsentIn(accepted=False, policy_version="1.0"), user, session
        )
    anonymize.assert_awaited_once_with(session, 7, reason="consent_revoked")
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(user)
    assert response.consent_required is True


async def test_delete_me_removes_user_and_returns_no_content():
    """Удаление аккаунта фиксируется в БД и возвращает ответ 204"""
    user = _user()
    session = AsyncMock()
    response = await delete_me(user, session)
    assert response.status_code == 204
    session.delete.assert_awaited_once_with(user)
    session.commit.assert_awaited_once()
