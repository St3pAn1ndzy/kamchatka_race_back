from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


def create_user_token(user_id: int, vk_user_id: int) -> tuple[str, int]:
    """Вернёт (token, expires_in_seconds)."""
    expires_in = settings.JWT_USER_TTL_SECONDS
    payload = {
        "sub": str(user_id),
        "vk_user_id": vk_user_id,
        "type": "user",
        "exp": datetime.now(tz=UTC) + timedelta(seconds=expires_in),
        "iat": datetime.now(tz=UTC),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def create_admin_token(admin_id: int, session_id: str) -> tuple[str, int]:
    expires_in = settings.ADMIN_SESSION_TTL_SECONDS
    payload = {
        "sub": str(admin_id),
        "session_id": session_id,
        "type": "admin",
        "exp": datetime.now(tz=UTC) + timedelta(seconds=expires_in),
        "iat": datetime.now(tz=UTC),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
