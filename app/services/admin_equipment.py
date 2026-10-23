"""Сервис состояния оборудования в админке"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.device import Device
from app.repositories.device import DeviceRepository
from app.schemas.admin_equipment import EquipmentHealthItem, EquipmentHealthResponse
from app.services.tracking_freshness import get_freshness_status

settings = get_settings()


def get_device_health_status(device: Device) -> str:
    """Возвращает единый технический статус для оборудования и карточки участника"""
    if not device.is_active:
        return "inactive"
    if device.sos_active:
        return "sos"
    if device.battery_percent is not None and device.battery_percent <= 20:
        return "low_battery"
    return "ok"


class AdminEquipmentService:
    """Бизнес-логика состояния трекеров для админки"""

    def __init__(self, session: AsyncSession) -> None:
        self.devices = DeviceRepository(session)

    async def get_health(self) -> EquipmentHealthResponse:
        now = datetime.now(tz=UTC)
        devices = await self.devices.list_for_health()

        items = []
        for device in devices:
            interval = (
                device.stage.tracker_interval_seconds
                if device.stage is not None
                else settings.TRACKING_POLL_INTERVAL_SECONDS
            )
            stale_after = interval * settings.TRACKING_STALE_MISSED_INTERVALS

            items.append(
                EquipmentHealthItem(
                    id=device.id,
                    iridium_number=device.iridium_number,
                    imei=device.imei,
                    name=device.name,
                    participant_id=device.participant_id,
                    stage_id=device.stage_id,
                    is_active=device.is_active,
                    battery_percent=device.battery_percent,
                    sos_active=device.sos_active,
                    last_message_at=device.last_message_at,
                    health_status=get_device_health_status(device),
                    freshness_status=get_freshness_status(
                        device.last_message_at,
                        now=now,
                        interval_seconds=interval,
                        stale_missed_intervals=settings.TRACKING_STALE_MISSED_INTERVALS,
                    ),
                    delayed_after_seconds=interval,
                    stale_after_seconds=stale_after,
                )
            )

        return EquipmentHealthResponse(items=items, total=len(items))
