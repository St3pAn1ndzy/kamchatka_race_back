"""Схемы административного API"""

from pydantic import Field

from app.schemas.base import BaseSchema


class AdminLoginRequest(BaseSchema):
    """Данные для входа администратора по логину и паролю"""

    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)


class AdminLoginResponse(BaseSchema):
    """JWT-токен администратора и время жизни сессии"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int