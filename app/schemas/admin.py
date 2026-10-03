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


class EquipmentHealthItem(BaseSchema):
    """Состояние одного трекера для админки"""

    id: int
    iridium_number: str
    imei: str
    name: str
    participant_id: int | None = None
    stage_id: int | None = None
    is_active: bool
    battery_percent: int | None = None
    sos_active: bool
    last_message_at: datetime | None = None
    health_status: str
    stale_after_seconds: int


class EquipmentHealthResponse(BaseSchema):
    """Сводка по состоянию оборудования"""

    items: list[EquipmentHealthItem]
    total: int


class DeviceAssignRequest(BaseSchema):
    """Данные для привязки трекера к участнику и этапу"""

    device_id: int = Field(gt=0)
    participant_id: int | None = Field(default=None, gt=0)
    stage_id: int | None = Field(default=None, gt=0)


class DeviceAssignResponse(BaseSchema):
    """Обновлённая привязка трекера"""

    id: int
    iridium_number: str
    imei: str
    name: str
    participant_id: int | None = None
    stage_id: int | None = None
    is_active: bool
