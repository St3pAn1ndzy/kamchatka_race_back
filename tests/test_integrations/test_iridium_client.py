"""Тесты IridiumClient — парсинг и fetch_positions.

Реальный формат Iridium360:
- LastKnownPosition + Track.Points
- Поля с большой буквы
- Battery только в LastKnownPosition
"""

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from app.integrations.iridium.client import IridiumClient


class TestParsePoint:
    """Парсинг одной точки (из LastKnownPosition или Track.Points)."""

    def test_success_with_battery(self) -> None:
        """LastKnownPosition со всеми полями."""
        client = IridiumClient(api_key="test")
        item = {
            "Id": "abc-123",
            "Date": "2026-10-08T14:32:00Z",
            "Lat": 62.123456,
            "Lon": 129.654321,
            "Cog": 45.0,
            "Sog": 12.5,
            "Alt": 850,
            "Battery": 87,
        }
        result = client._parse_point(item, "123456", with_battery=True)
        assert result is not None
        assert result.iridium_number == "123456"
        assert result.iridium_point_id == "abc-123"
        assert result.lat == 62.123456
        assert result.lon == 129.654321
        assert result.recorded_at == datetime(2026, 10, 8, 14, 32, tzinfo=UTC)
        assert result.course_deg == 45.0
        assert result.speed_kmh == 12.5
        assert result.altitude_m == 850
        assert result.battery_percent == 87

    def test_track_point_no_battery(self) -> None:
        """Track.Points — Battery не парсится (with_battery=False)."""
        client = IridiumClient(api_key="test")
        item = {
            "Id": "abc-122",
            "Date": "2026-10-08T14:12:00Z",
            "Lat": 62.12,
            "Lon": 129.65,
            "Cog": 44.0,
            "Sog": 12.0,
            "Alt": 848,
            "Battery": 90,
        }
        result = client._parse_point(item, "123456", with_battery=False)
        assert result is not None
        assert result.battery_percent is None  # with_battery=False

    def test_missing_lat(self) -> None:
        """Нет Lat → KeyError → None."""
        client = IridiumClient(api_key="test")
        item = {"Id": "abc-123", "Date": "2026-10-08T14:32:00Z"}
        result = client._parse_point(item, "123456", with_battery=False)
        assert result is None

    def test_bad_lat(self) -> None:
        """Lat не число → TypeError → None."""
        client = IridiumClient(api_key="test")
        item = {
            "Id": "abc-123",
            "Date": "2026-10-08T14:32:00Z",
            "Lat": "abc",
            "Lon": 129.65,
        }
        result = client._parse_point(item, "123456", with_battery=False)
        assert result is None

    def test_optional_fields_none(self) -> None:
        """Cog/Sog/Alt/Battery отсутствуют → None."""
        client = IridiumClient(api_key="test")
        item = {
            "Id": "abc-123",
            "Date": "2026-10-08T14:32:00Z",
            "Lat": 62.12,
            "Lon": 129.65,
        }
        result = client._parse_point(item, "123456", with_battery=True)
        assert result is not None
        assert result.course_deg is None
        assert result.speed_kmh is None
        assert result.altitude_m is None
        assert result.battery_percent is None  # Battery нет в item → with_battery не спасает


class TestParseDate:
    """Метод _parse_date — ISO-8601 и Unix timestamp."""

    def test_iso(self) -> None:
        """ISO-8601 с 'Z' → datetime с tz."""
        client = IridiumClient(api_key="x")
        dt = client._parse_date("2026-10-08T14:32:00Z")
        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_unix(self) -> None:
        """Unix timestamp (int) → datetime с tz."""
        client = IridiumClient(api_key="x")
        dt = client._parse_date(1728391920)
        assert dt.tzinfo is not None

    def test_iso_with_offset(self) -> None:
        """ISO с явным смещением парсится без 'Z'."""
        client = IridiumClient(api_key="x")
        dt = client._parse_date("2026-10-08T14:32:00+03:00")
        assert dt.year == 2026

    def test_iso_without_offset_is_utc(self) -> None:
        client = IridiumClient(api_key="x")
        dt = client._parse_date("2026-10-08T14:32:00")
        assert dt == datetime(2026, 10, 8, 14, 32, tzinfo=UTC)

    def test_bad_type(self) -> None:
        """Неожиданный тип → ValueError."""
        client = IridiumClient(api_key="x")
        with pytest.raises(ValueError):
            client._parse_date(None)


class TestParseDevice:
    """Парсинг устройства: LastKnownPosition + Track.Points."""

    def test_full_device(self) -> None:
        """LastKnownPosition + Track.Points."""
        client = IridiumClient(api_key="test")
        item = {
            "Name": "Трекер 1",
            "Number": "123456",
            "Imei": "300234000000000",
            "LastKnownPosition": {
                "Id": "abc-100",
                "Date": "2026-10-08T14:32:00Z",
                "Lat": 62.12,
                "Lon": 129.65,
                "Cog": 45.0,
                "Sog": 12.5,
                "Alt": 850,
                "Battery": 87,
            },
            "Track": {
                "Points": [
                    {
                        "Id": "abc-99",
                        "Date": "2026-10-08T14:12:00Z",
                        "Lat": 62.10,
                        "Lon": 129.63,
                        "Cog": 44.0,
                        "Sog": 12.0,
                        "Alt": 848,
                    },
                ],
            },
        }
        result = client._parse_device(item)
        assert len(result) == 2

        # LastKnownPosition — батарея есть
        lkp = result[0]
        assert lkp.iridium_point_id == "abc-100"
        assert lkp.battery_percent == 87
        assert lkp.iridium_number == "123456"

        # Track.Point — батареи нет
        track = result[1]
        assert track.iridium_point_id == "abc-99"
        assert track.battery_percent is None

    def test_only_last_known(self) -> None:
        """Только LastKnownPosition, Track отсутствует."""
        client = IridiumClient(api_key="test")
        item = {
            "Number": "123456",
            "LastKnownPosition": {
                "Id": "abc-100",
                "Date": "2026-10-08T14:32:00Z",
                "Lat": 62.12,
                "Lon": 129.65,
            },
        }
        result = client._parse_device(item)
        assert len(result) == 1

    def test_empty_track(self) -> None:
        """Track есть, но Points пустой."""
        client = IridiumClient(api_key="test")
        item = {
            "Number": "123456",
            "LastKnownPosition": {
                "Id": "abc-100",
                "Date": "2026-10-08T14:32:00Z",
                "Lat": 62.12,
                "Lon": 129.65,
            },
            "Track": {"Points": []},
        }
        result = client._parse_device(item)
        assert len(result) == 1  # только LastKnownPosition

    def test_no_position(self) -> None:
        """Нет LastKnownPosition и нет Track → пусто."""
        client = IridiumClient(api_key="test")
        item = {"Number": "123456"}
        result = client._parse_device(item)
        assert result == []


class TestFetchPositions:
    """fetch_positions — интеграция с httpx."""

    @pytest.mark.asyncio
    async def test_no_key(self) -> None:
        """api_key='' → [] без HTTP."""
        client = IridiumClient(api_key="")
        result = await client.fetch_positions([("001", None)])
        assert result == []

    @pytest.mark.asyncio
    async def test_timeout_continues(self) -> None:
        """Таймаут на одном устройстве — continue без retry."""

        async def mock_get(*args, **kwargs) -> httpx.Response:
            raise httpx.TimeoutException("timeout")

        with patch("httpx.AsyncClient.get", mock_get):
            client = IridiumClient(api_key="real_key")
            result = await client.fetch_positions([("001", None)])
            assert result == []

    @pytest.mark.asyncio
    async def test_http_error_continues(self) -> None:
        """HTTP-ошибка на одном устройстве — continue."""

        async def mock_get(*args, **kwargs) -> None:
            resp = httpx.Response(403, request=httpx.Request("GET", "http://example.com"))
            raise httpx.HTTPStatusError("forbidden", request=resp.request, response=resp)

        with patch("httpx.AsyncClient.get", mock_get):
            client = IridiumClient(api_key="real_key")
            result = await client.fetch_positions([("001", None)])
            assert result == []

    @pytest.mark.asyncio
    async def test_non_list_response(self) -> None:
        """Ответ не list → [] с warning."""

        async def mock_get(*args, **kwargs) -> httpx.Response:
            return httpx.Response(
                200, json={"not": "a list"}, request=httpx.Request("GET", "http://example.com")
            )

        with patch("httpx.AsyncClient.get", mock_get):
            client = IridiumClient(api_key="real_key")
            result = await client.fetch_positions([("001", None)])
            assert result == []

    @pytest.mark.asyncio
    async def test_multiple_devices_one_fails(self) -> None:
        """Два устройства, второе падает — первое парсится."""
        call_count = 0

        async def mock_get(*args, **kwargs) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json=[
                        {
                            "Number": "001",
                            "LastKnownPosition": {
                                "Id": "p1",
                                "Date": "2026-10-08T14:32:00Z",
                                "Lat": 62.0,
                                "Lon": 129.0,
                            },
                        },
                    ],
                    request=httpx.Request("GET", "http://example.com"),
                )
            raise httpx.TimeoutException("timeout")

        with patch("httpx.AsyncClient.get", mock_get):
            client = IridiumClient(api_key="real_key")
            result = await client.fetch_positions([("001", None), ("002", None)])
            assert len(result) == 1
            assert result[0].iridium_number == "001"

    @pytest.mark.asyncio
    async def test_with_last_point_id(self) -> None:
        """Передан last_point_id — используется point_id_from вместо date_from."""

        async def mock_get(*args, **kwargs) -> httpx.Response:
            params = kwargs.get("params")
            # Проверяем, что в params есть point_id_from, а не date_from
            assert params is not None
            assert "point_id_from" in params
            assert "date_from" not in params
            assert params["point_id_from"] == "abc-100"
            return httpx.Response(
                200,
                json=[],
                request=httpx.Request("GET", "http://example.com"),
            )

        with patch("httpx.AsyncClient.get", mock_get):
            client = IridiumClient(api_key="real_key")
            result = await client.fetch_positions([("001", "abc-100")])
            assert result == []

    @pytest.mark.asyncio
    async def test_without_last_point_id(self) -> None:
        """Без last_point_id — используется date_from."""

        async def mock_get(*args, **kwargs) -> httpx.Response:
            params = kwargs.get("params")
            assert params is not None
            assert "date_from" in params
            assert "point_id_from" not in params
            return httpx.Response(
                200,
                json=[],
                request=httpx.Request("GET", "http://example.com"),
            )

        with patch("httpx.AsyncClient.get", mock_get):
            client = IridiumClient(api_key="real_key")
            result = await client.fetch_positions([("001", None)])
            assert result == []
