"""Авторизация администраторов для API"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import SessionDep
from app.config import get_settings
from app.db.models.admin_account import AdminAccount
from app.db.models.admin_session import AdminSession
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse
from app.security.passwords import verify_password
from app.security.tokens import create_admin_token

router = APIRouter(prefix="/auth", tags=["admin-auth"])
settings = get_settings()


@router.post("/login", response_model=AdminLoginResponse)
async def login_admin(body: AdminLoginRequest, session: SessionDep) -> AdminLoginResponse:
    """Проверяем логин/пароль администратора и выдаем JWT"""
    admin = (
        await session.execute(select(AdminAccount).where(AdminAccount.login == body.login))
    ).scalar_one_or_none()

    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    if not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Администратор отключён")
    if not admin.password_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    if not verify_password(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")

    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.ADMIN_SESSION_TTL_SECONDS)

    admin_session = AdminSession(
        session_id=session_id,
        admin_id=admin.id,
        expires_at=expires_at,
    )
    session.add(admin_session)
    await session.commit()

    token, expires_in = create_admin_token(admin.id, session_id)
    return AdminLoginResponse(access_token=token, expires_in=expires_in)
