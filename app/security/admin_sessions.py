"""Общие функции для admin-сессий"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.db.models.audit_log import AuditLog
from app.security.passwords import verify_password

settings = get_settings()


async def authenticate_admin_by_password(
    session: AsyncSession,
    login: str,
    password: str,
) -> AdminAccount | None:
    """Проверяем логин и пароль администратора"""
    admin = (
        await session.execute(select(AdminAccount).where(AdminAccount.login == login))
    ).scalar_one_or_none()

    if admin is None or not admin.is_active or not admin.password_hash:
        return None
    if not verify_password(password, admin.password_hash):
        return None

    return admin


async def create_admin_session(
    session: AsyncSession,
    admin: AdminAccount,
    *,
    surface: str,
) -> AdminSession:
    """Создаём серверную сессию администратора и пишем вход в аудит"""
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.ADMIN_SESSION_TTL_SECONDS)

    admin_session = AdminSession(
        session_id=session_id,
        admin_id=admin.id,
        expires_at=expires_at,
    )
    session.add(admin_session)
    await session.flush()

    session.add(
        AuditLog(
            admin_id=admin.id,
            action="admin_login",
            entity_type="admin_session",
            entity_id=str(admin_session.id),
            payload={"surface": surface},
        )
    )
    await session.flush()

    return admin_session


async def get_active_admin_for_session(
    session: AsyncSession,
    session_id: str,
    *,
    admin_id: int | None = None,
) -> AdminAccount | None:
    """Возвращаем админа только если серверная сессия жива"""
    admin_session = (
        await session.execute(select(AdminSession).where(AdminSession.session_id == session_id))
    ).scalar_one_or_none()

    if admin_session is None:
        return None
    if admin_session.revoked_at is not None:
        return None
    if admin_session.expires_at <= datetime.now(tz=UTC):
        return None
    if admin_id is not None and admin_session.admin_id != admin_id:
        return None

    admin = await session.get(AdminAccount, admin_session.admin_id)
    if admin is None or not admin.is_active:
        return None

    return admin


async def revoke_admin_session(
    session: AsyncSession,
    session_id: str,
    *,
    surface: str,
) -> AdminSession | None:
    """Отзываем серверную сессию администратора и пишем выход в аудит"""
    admin_session = (
        await session.execute(select(AdminSession).where(AdminSession.session_id == session_id))
    ).scalar_one_or_none()

    if admin_session is None:
        return None

    if admin_session.revoked_at is None:
        admin_session.revoked_at = datetime.now(tz=UTC)
        session.add(
            AuditLog(
                admin_id=admin_session.admin_id,
                action="admin_logout",
                entity_type="admin_session",
                entity_id=str(admin_session.id),
                payload={"surface": surface},
            )
        )
        await session.flush()

    return admin_session
