"""Состояние оборудования в административном API"""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminDep, SessionDep
from app.config import get_settings
from app.db.models.device import Device
from app.schemas.admin import EquipmentHealthItem, EquipmentHealthResponse

router = APIRouter(prefix="/equipment", tags=["admin-equipment"])
settings = get_settings()


def _device_health_status(device: Device, now: datetime, stale_after_seconds: int) -> str:
    """Собираем короткий статус трекера для админки"""
    if not device.is_active:
        return "inactive"
    if device.sos_active:
        return "sos"
    if device.last_message_at is None:
        return "no_signal"

    seconds_since_message = (now - device.last_message_at).total_seconds()
    if seconds_since_message > stale_after_seconds:
        return "stale"

    if device.battery_percent is not None and device.battery_percent <= 20:
        return "low_battery"

    return "ok"


@router.get("/health", response_model=EquipmentHealthResponse)
async def equipment_health(
    session: SessionDep,
    _admin: AdminDep,
) -> EquipmentHealthResponse:
    """Возвращаем состояние всех трекеров для админки"""
    stale_after_seconds = (
        settings.TRACKING_POLL_INTERVAL_SECONDS * settings.TRACKING_STALE_MISSED_INTERVALS
    )
    now = datetime.now(tz=UTC)

    stmt = select(Device).order_by(Device.is_active.desc(), Device.name.asc(), Device.id.asc())
    devices = list((await session.execute(stmt)).scalars().all())

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
            health_status=_device_health_status(device, now, stale_after_seconds),
            stale_after_seconds=stale_after_seconds,
        )
        for device in devices
    ]

    return EquipmentHealthResponse(items=items, total=len(items))
