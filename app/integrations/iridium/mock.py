"""Мок-клиент Iridium360 для dev.

Генерирует случайные позиции в районе Камчатки.
Нужен, пока нет реального ключа или БД пустая.
"""

import logging
import random
from datetime import UTC, datetime, timedelta

from app.integrations.iridium.client import IridiumPosition

logger = logging.getLogger("avacha.iridium")

BASE_LAT = 62.0
BASE_LON = 129.0
LAT_SPREAD = 1.5
LON_SPREAD = 1.5


class MockIridiumClient:
    """Генерирует правдоподобные позиции для тестирования."""

    async def fetch_positions(
        self,
        devices: list[tuple[str, str | None]],
    ) -> list[IridiumPosition]:
        if not devices:
            return []

        now = datetime.now(tz=UTC)
        positions: list[IridiumPosition] = []

        for iridium_number, _ in devices:
            lat = BASE_LAT + random.uniform(-LAT_SPREAD, LAT_SPREAD)
            lon = BASE_LON + random.uniform(-LON_SPREAD, LON_SPREAD)
            recorded_at = now - timedelta(minutes=random.randint(0, 20))

            positions.append(
                IridiumPosition(
                    iridium_number=str(iridium_number),
                    iridium_point_id=f"mock-{random.randint(100000, 999999)}",
                    lat=round(lat, 6),
                    lon=round(lon, 6),
                    recorded_at=recorded_at,
                    course_deg=round(random.uniform(0, 360), 1),
                    speed_kmh=round(random.uniform(5.0, 15.0), 1),
                    altitude_m=round(random.uniform(100, 1200), 1),
                    battery_percent=random.randint(20, 100),
                )
            )

        logger.debug("MockIridiumClient сгенерировал %d позиций", len(positions))
        return positions
