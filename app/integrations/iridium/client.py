"""Клиент Iridium360 API.

Реальный формат (проверено по документации Iridium360):
- Поля с большой буквы: Name, Number, Imei, LastKnownPosition, Track.
- LastKnownPosition — последняя точка (всегда).
- Track.Points — история (только если include_track=true).
- Battery — только в LastKnownPosition.
- SOS в API нет.
- Параметр запроса — number (не imei).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger("avacha.iridium")
settings = get_settings()


@dataclass
class IridiumPosition:
    """Нормализованная позиция от Iridium360."""

    iridium_number: str
    iridium_point_id: str
    lat: float
    lon: float
    recorded_at: datetime
    course_deg: float | None = None  # Cog
    speed_kmh: float | None = None  # Sog
    altitude_m: float | None = None  # Alt
    battery_percent: int | None = None  # Battery — только LastKnownPosition


class IridiumClientProtocol(Protocol):
    """Интерфейс клиента. Позволяет подменить реализацию (мок)."""

    async def fetch_positions(
        self,
        devices: list[tuple[str, str | None]],
    ) -> list[IridiumPosition]: ...


class IridiumClient:
    """Реализация клиента Iridium360 API.

    Один HTTP-запрос на устройство (API не принимает список).
    При ошибке на одном устройстве — continue, остальные продолжают.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key or settings.IRIDIUM_API_KEY
        self.base_url = (base_url or settings.IRIDIUM_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.IRIDIUM_REQUEST_TIMEOUT_SECONDS

    async def fetch_positions(
        self,
        devices: list[tuple[str, str | None]],
    ) -> list[IridiumPosition]:
        """Опрос Iridium360. Один запрос на устройство.

        Принимает список кортежей (iridium_number, last_point_id).
        Если last_point_id задан — запрос с point_id_from,
        иначе — date_from (последние 2 часа).
        """
        if not self.api_key:
            return []

        positions: list[IridiumPosition] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for number, last_point_id in devices:
                params: dict[str, str] = {
                    "token": self.api_key,
                    "number": number,
                    "include_track": "true",
                }
                if last_point_id:
                    params["point_id_from"] = last_point_id
                else:
                    params["date_from"] = (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat()

                try:
                    resp = await client.get(
                        f"{self.base_url}{settings.IRIDIUM_DEVICES_PATH}",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.TimeoutException:
                    logger.warning("iridium_timeout", extra={"number": number})
                    continue
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "iridium_http_error",
                        extra={"number": number, "status": exc.response.status_code},
                    )
                    continue
                except httpx.RequestError as exc:
                    logger.warning(
                        "iridium_request_error",
                        extra={"number": number, "error": str(exc)},
                    )
                    continue

                if not isinstance(data, list) or not data:
                    continue

                positions.extend(self._parse_device(data[0]))

        return positions

    def _parse_device(self, item: dict) -> list[IridiumPosition]:
        """Парсит устройство: LastKnownPosition + Track.Points."""
        positions: list[IridiumPosition] = []
        iridium_number = str(item.get("Number", ""))

        lkp = item.get("LastKnownPosition")
        if isinstance(lkp, dict):
            parsed = self._parse_point(lkp, iridium_number, with_battery=True)
            if parsed is not None:
                positions.append(parsed)

        track = item.get("Track")
        if isinstance(track, dict):
            for point in track.get("Points", []):
                parsed = self._parse_point(point, iridium_number, with_battery=False)
                if parsed is not None:
                    positions.append(parsed)

        return positions

    def _parse_point(
        self,
        item: dict,
        iridium_number: str,
        *,
        with_battery: bool,
    ) -> IridiumPosition | None:
        """Парсит одну точку. При ошибке — None.

        Поддерживает Date в ISO-8601 и Unix timestamp.
        Уточнить при первом реальном запросе.
        """
        try:
            return IridiumPosition(
                iridium_number=iridium_number,
                iridium_point_id=str(item.get("Id", "")),
                lat=float(item["Lat"]),
                lon=float(item["Lon"]),
                recorded_at=self._parse_date(item["Date"]),
                course_deg=float(item["Cog"]) if item.get("Cog") is not None else None,
                speed_kmh=float(item["Sog"]) if item.get("Sog") is not None else None,
                altitude_m=float(item["Alt"]) if item.get("Alt") is not None else None,
                battery_percent=(
                    int(item["Battery"])
                    if with_battery and item.get("Battery") is not None
                    else None
                ),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("iridium_parse_failed", extra={"error": str(exc)})
            return None

    def _parse_date(self, raw: object) -> datetime:
        """Парсит Date из Iridium: ISO-8601 или Unix timestamp."""
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, tz=UTC)
        if isinstance(raw, str):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        raise ValueError(f"Unexpected Date type: {type(raw).__name__}")
