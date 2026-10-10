"""Celery-задача опроса Iridium360."""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models.device import Device
from app.db.models.track_point import TrackPoint
from app.integrations.iridium import get_iridium_client
from app.tasks.celery_app import celery_app

logger = logging.getLogger("avacha.tracking")


@celery_app.task(name="app.tasks.tracking.poll_iridium")
def poll_iridium() -> dict:
    """Опрос Iridium360. Запускается Celery Beat по расписанию."""
    return asyncio.run(_poll_iridium())


async def _poll_iridium() -> dict:
    client = get_iridium_client()

    async with async_session_factory() as session:
        devices = (
            (await session.execute(select(Device).where(Device.is_active.is_(True))))
            .scalars()
            .all()
        )

        if not devices:
            logger.info("iridium_poll_no_devices")
            return {"devices": 0, "ingested": 0, "duplicated": 0}

        # Для каждого device — последний iridium_point_id из БД
        device_args: list[tuple[str, str | None]] = []
        devices_by_number: dict[str, Device] = {}

        for d in devices:
            if not d.iridium_number:
                continue
            last_point_id = (
                await session.execute(
                    select(TrackPoint.iridium_point_id)
                    .where(
                        TrackPoint.device_id == d.id,
                        TrackPoint.iridium_point_id.is_not(None),
                    )
                    .order_by(TrackPoint.recorded_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            device_args.append((d.iridium_number, last_point_id))
            devices_by_number[d.iridium_number] = d

        if not device_args:
            logger.info("iridium_poll_no_numbers")
            return {"devices": 0, "ingested": 0, "duplicated": 0}

        positions = await client.fetch_positions(device_args)

        ingested = 0
        duplicated = 0

        for pos in positions:
            device = devices_by_number.get(pos.iridium_number)
            if device is None:
                continue

            # Дедупликация: по sha256(number:point_id), fallback — по sha256(number:date)
            if pos.iridium_point_id:
                dedup_key = hashlib.sha256(
                    f"{pos.iridium_number}:{pos.iridium_point_id}".encode()
                ).hexdigest()
                existing = (
                    await session.execute(
                        select(TrackPoint.id).where(TrackPoint.deduplication_key == dedup_key)
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    duplicated += 1
                    continue
            else:
                dedup_key = hashlib.sha256(
                    f"{pos.iridium_number}:{pos.recorded_at.isoformat()}".encode()
                ).hexdigest()
                existing = (
                    await session.execute(
                        select(TrackPoint.id).where(TrackPoint.deduplication_key == dedup_key)
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    duplicated += 1
                    continue

            session.add(
                TrackPoint(
                    device_id=device.id,
                    participant_id=device.participant_id,
                    stage_id=device.stage_id,
                    iridium_point_id=pos.iridium_point_id or None,
                    lat=pos.lat,
                    lon=pos.lon,
                    altitude=pos.altitude_m,
                    course_deg=pos.course_deg,
                    source_speed=pos.speed_kmh,
                    recorded_at=pos.recorded_at,
                    received_at=datetime.now(tz=UTC),
                    deduplication_key=dedup_key,
                    is_confirmed=True,
                )
            )
            ingested += 1

            if device.last_message_at is None or pos.recorded_at > device.last_message_at:
                device.last_message_at = pos.recorded_at
            if pos.battery_percent is not None:
                device.battery_percent = pos.battery_percent

        await session.commit()

    logger.info(
        "iridium_poll_done",
        extra={"devices": len(devices), "ingested": ingested, "duplicated": duplicated},
    )
    return {"devices": len(devices), "ingested": ingested, "duplicated": duplicated}
