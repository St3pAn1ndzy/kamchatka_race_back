"""Сервис состояния оборудования в админке"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.device import Device
from app.repositories.device import DeviceRepository
from app.schemas.admin_equipment import EquipmentHealthItem, EquipmentHealthResponse

settings = get_settings()


class AdminEquipmentService:
    """Бизнес-логика состояния трекеров для админки"""

    def __init__(self, session: AsyncSession) -> None:
        self.devices = DeviceRepository(session)

    @staticmethod
    def _device_freshness_status(
        device: Device,
        *,
        now: datetime,
        delayed_after_seconds: int,
        stale_after_seconds: int,
    ) -> str:
        """Показываем, насколько свежие данные пришли от трекера"""
        if device.last_message_at is None:
            return "no_signal"

        seconds_since_message = (now - device.last_message_at).total_seconds()
        if seconds_since_message > stale_after_seconds:
            return "stale"
        if seconds_since_message > delayed_after_seconds:
            return "delayed"

        return "fresh"

    @staticmethod
    def _device_health_status(device: Device) -> str:
        """Собираем короткий технический статус трекера"""
        if not device.is_active:
            return "inactive"
        if device.sos_active:
            return "sos"
        if device.battery_percent is not None and device.battery_percent <= 20:
            return "low_battery"

        return "ok"

    async def get_health(self) -> EquipmentHealthResponse:
        """Возвращаем состояние всех трекеров"""
        delayed_after_seconds = settings.TRACKING_POLL_INTERVAL_SECONDS
        stale_after_seconds = (
            settings.TRACKING_POLL_INTERVAL_SECONDS * settings.TRACKING_STALE_MISSED_INTERVALS
        )
        now = datetime.now(tz=UTC)
        devices = await self.devices.list_for_health()

        items = [
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
                health_status=self._device_health_status(
                    device,
                ),
                freshness_status=self._device_freshness_status(
                    device,
                    now=now,
                    delayed_after_seconds=delayed_after_seconds,
                    stale_after_seconds=stale_after_seconds,
                ),
                delayed_after_seconds=delayed_after_seconds,
                stale_after_seconds=stale_after_seconds,
            )
            for device in devices
        ]

        return EquipmentHealthResponse(items=items, total=len(items))
