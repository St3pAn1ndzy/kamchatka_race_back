"""Авторизация администраторов для API"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse
from app.security.admin_sessions import authenticate_admin_by_password, create_admin_session
from app.security.tokens import create_admin_token

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    responses={
        429: {"description": "Превышен общий для API и админки лимит входов с одного IP"},
        503: {"description": "Счётчик попыток входа временно недоступен"},
    },
)
async def login_admin(body: AdminLoginRequest, session: SessionDep) -> AdminLoginResponse:
    """Проверяем логин/пароль администратора и выдаём JWT"""
    admin = await authenticate_admin_by_password(session, body.login, body.password)
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")

    admin_session = await create_admin_session(session, admin, surface="api")
    await session.commit()

    token, expires_in = create_admin_token(admin.id, admin_session.session_id)
    return AdminLoginResponse(access_token=token, expires_in=expires_in)
