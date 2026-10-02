"""Зависимости FastAPI: сессия БД, текущий пользователь, админ.

`decode_token` возвращает None при ошибке — не бросает исключение.
`sub` в JWT — строка, поэтому `int(payload["sub"])`.
`type` в payload — `user` или `admin`, проверяем.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.user import User
from app.repositories import (
    FanSubscriptionRepository,
    FAQItemRepository,
    NewsPostRepository,
    ParticipantRepository,
    ScheduleEventRepository,
    UserRepository,
)
from app.security.tokens import decode_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


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


async def get_optional_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    token = _extract_bearer(authorization)
    if token is None:
        return None

    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "user":
        return None

    sub = payload.get("sub")
    if sub is None:
        return None

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None

    return await session.get(User, user_id)


async def get_current_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    return user


async def require_admin(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AdminAccount:
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")

    payload = _decode_admin_payload(token)
    admin_id = int(payload["sub"])
    session_id = payload["session_id"]

    admin_session = (
        await session.execute(select(AdminSession).where(AdminSession.session_id == session_id))
    ).scalar_one_or_none()
    if admin_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия не найдена")
    if admin_session.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия отозвана")

    admin = await session.get(AdminAccount, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступ запрещён")
    return admin


CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]
AdminDep = Annotated[AdminAccount, Depends(require_admin)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
FAQItemRepoDep = Annotated[FAQItemRepository, Depends(get_faq_item_repo)]
NewsPostRepoDep = Annotated[NewsPostRepository, Depends(get_news_post_repo)]
ScheduleEventRepoDep = Annotated[ScheduleEventRepository, Depends(get_schedule_event_repo)]
ParticipantRepoDep = Annotated[ParticipantRepository, Depends(get_participant_repo)]
FanSubscriptionRepoDep = Annotated[FanSubscriptionRepository, Depends(get_fan_subscription_repo)]
