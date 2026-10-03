"""Схемы административного API"""

from datetime import datetime

from pydantic import Field

from app.enums import RaceState
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


class RaceStatusUpdateRequest(BaseSchema):
    """Данные для обновления статуса гонки"""

    status: RaceState
    current_stage_id: int | None = None


class RaceStatusResponse(BaseSchema):
    """Текущий статус гонки"""

    id: int
    status: RaceState
    current_stage_id: int | None = None
    updated_at: datetime
