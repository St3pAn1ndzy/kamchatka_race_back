"""Зависимости FastAPI: сессия БД, текущий пользователь, админ.

`decode_token` возвращает None при ошибке — не бросает исключение.
`sub` в JWT — строка, поэтому `int(payload["sub"])`.
`type` в payload — `user` или `admin`, проверяем.

Используем HTTPBearer — он даёт кнопку «Authorize» в /docs и
корректные замки у защищённых эндпоинтов. Роутеры это не меняет:
они по-прежнему используют CurrentUserDep / OptionalUserDep / AdminDep.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models.admin_account import AdminAccount
from app.db.models.user import User
from app.repositories import (
    FanSubscriptionRepository,
    FAQItemRepository,
    NewsPostRepository,
    NotificationQueueRepository,
    ParticipantRepository,
    ScheduleEventRepository,
    UserRepository,
)
from app.repositories.viewer_location import ViewerLocationRepository
from app.security.admin_sessions import get_active_admin_for_session
from app.security.tokens import decode_token
from app.services.results import ResultService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False — при отсутствии заголовка не бросаем 403 автоматически,
# а отдаём None. Это нужно для get_optional_user.
_bearer = HTTPBearer(auto_error=False)


# --- Репозитории -------------------------------------------------------------


def get_user_repo(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_faq_item_repo(session: SessionDep) -> FAQItemRepository:
    return FAQItemRepository(session)


def get_news_post_repo(session: SessionDep) -> NewsPostRepository:
    return NewsPostRepository(session)


def get_schedule_event_repo(session: SessionDep) -> ScheduleEventRepository:
    return ScheduleEventRepository(session)


def get_participant_repo(session: SessionDep) -> ParticipantRepository:
    return ParticipantRepository(session)


def get_fan_subscription_repo(session: SessionDep) -> FanSubscriptionRepository:
    return FanSubscriptionRepository(session)


def get_notification_queue_repo(session: SessionDep) -> NotificationQueueRepository:
    return NotificationQueueRepository(session)


def get_result_service(session: SessionDep) -> ResultService:
    return ResultService(session)


def get_viewer_location_repo(session: SessionDep) -> ViewerLocationRepository:
    return ViewerLocationRepository(session)


# --- Вспомогательные ---------------------------------------------------------


def _decode_user_payload(token: str) -> dict:
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный или истёкший токен")
    if payload.get("type") != "user":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный тип токена")
    if "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Токен без user_id")
    return payload


def _decode_admin_payload(token: str) -> dict:
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный или истёкший токен")
    if payload.get("type") != "admin":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный тип токена")
    if "sub" not in payload or "session_id" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Токен без admin_id или session_id")
    return payload


async def _load_user(session: AsyncSession, token: str) -> User | None:
    """Загрузить пользователя по токену. None — если токен невалиден."""
    payload = decode_token(token)
    if payload is None or payload.get("type") != "user":
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    return await session.get(User, user_id)


# --- Пользователь: опциональная авторизация ----------------------------------


async def get_optional_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """Опциональная авторизация. None, если токена нет или он невалиден."""
    if credentials is None:
        return None
    return await _load_user(session, credentials.credentials)


# --- Пользователь: обязательная авторизация ----------------------------------


async def get_current_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    """Обязательная авторизация. 401, если токена нет или он невалиден."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    return user


# --- Админ: обязательная авторизация + серверная сессия ----------------------


async def require_admin(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AdminAccount:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")

    payload = _decode_admin_payload(credentials.credentials)
    admin_id = int(payload["sub"])
    session_id = payload["session_id"]

    admin = await get_active_admin_for_session(session, session_id, admin_id=admin_id)
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия не найдена или истекла")

    return admin


# --- Annotated-алиасы (роутеры не меняются) ----------------------------------

CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]
AdminDep = Annotated[AdminAccount, Depends(require_admin)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
FAQItemRepoDep = Annotated[FAQItemRepository, Depends(get_faq_item_repo)]
NewsPostRepoDep = Annotated[NewsPostRepository, Depends(get_news_post_repo)]
ScheduleEventRepoDep = Annotated[ScheduleEventRepository, Depends(get_schedule_event_repo)]
ParticipantRepoDep = Annotated[ParticipantRepository, Depends(get_participant_repo)]
FanSubscriptionRepoDep = Annotated[FanSubscriptionRepository, Depends(get_fan_subscription_repo)]
NotificationQueueRepoDep = Annotated[
    NotificationQueueRepository, Depends(get_notification_queue_repo)
]
ResultServiceDep = Annotated[ResultService, Depends(get_result_service)]
ViewerLocationRepoDep = Annotated[ViewerLocationRepository, Depends(get_viewer_location_repo)]
