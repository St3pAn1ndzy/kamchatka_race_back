import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.config import get_settings
from app.db.models.device import Device
from app.db.models.stage import Stage
from app.schemas.admin_equipment import EquipmentHealthItem
from app.services.admin_equipment import AdminEquipmentService


def _make_device(*, age_seconds: int, stage: Stage | None) -> Device:
    device = Device(
        id=1,
        iridium_number="001",
        imei="300234000000001",
        name="Test tracker",
        is_active=True,
        sos_active=False,
        battery_percent=80,
        last_message_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
    )
    device.stage = stage
    return device


def _get_health_item(device: Device) -> EquipmentHealthItem:
    service = AdminEquipmentService(AsyncMock())
    service.devices.list_for_health = AsyncMock(return_value=[device])
    response = asyncio.run(service.get_health())
    assert response.total == 1
    return response.items[0]


def test_health_uses_stage_transmission_interval() -> None:
    stage = Stage(id=1, name="Test stage", tracker_interval_seconds=60)
    item = _get_health_item(_make_device(age_seconds=90, stage=stage))

    assert item.freshness_status == "delayed"
    assert item.delayed_after_seconds == 60
    assert item.stale_after_seconds == 60 * get_settings().TRACKING_STALE_MISSED_INTERVALS


def test_health_without_stage_uses_poll_interval() -> None:
    interval = get_settings().TRACKING_POLL_INTERVAL_SECONDS
    item = _get_health_item(_make_device(age_seconds=interval + max(1, interval // 2), stage=None))

    assert item.freshness_status == "delayed"
    assert item.delayed_after_seconds == interval
    assert item.stale_after_seconds == interval * get_settings().TRACKING_STALE_MISSED_INTERVALS
