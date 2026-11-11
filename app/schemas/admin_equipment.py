"""Схемы состояния оборудования для админки"""

from datetime import datetime

from app.schemas.base import BaseSchema


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
    freshness_status: str
    delayed_after_seconds: int
    stale_after_seconds: int


class EquipmentHealthResponse(BaseSchema):
    """Сводка по состоянию оборудования"""

    items: list[EquipmentHealthItem]
    total: int
