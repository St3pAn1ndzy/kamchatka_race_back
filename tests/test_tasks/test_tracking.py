"""Тесты Celery-задачи poll_iridium (реальный формат Iridium360)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.device import Device
from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint


class FakeCM:
    """Async-контекст-менеджер, возвращающий мок-сессию."""

    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc) -> None:
        return None


def _make_device(
    iridium_number: str = "001",
    device_id: int = 1,
) -> Device:
    dev = Device(
        id=device_id,
        imei=f"30023400000000{device_id}",
        iridium_number=iridium_number,
        name="Test Device",
        is_active=True,
        sos_active=False,
        battery_percent=None,
        last_message_at=None,
    )
    dev.participant_id = 1
    dev.stage_id = 1
    return dev


def _make_session(
    devices: list[Device],
    last_point_ids: list[str | None] | None = None,
    existing_point_id: int | None = None,
) -> AsyncMock:
    """Собирает мок сессии с side_effect для execute().

    Порядок вызовов execute():
    1. select(Device)                        → .scalars().all() → devices
    2..N. select(TrackPoint.iridium_point_id) → .scalar_one_or_none() → last_point_id
    N+1..M. select(TrackPoint.id)             → .scalar_one_or_none() → existing_point_id
    """
    session = AsyncMock()

    # session.add / commit — реально синхронные/асинхронные методы SQLAlchemy-сессии
    session.add = MagicMock()
    session.commit = AsyncMock()

    # 1. Device list
    device_result = MagicMock()
    device_result.scalars.return_value.all.return_value = devices

    # 2. Last point ID queries (one per device with iridium_number)
    side: list = [device_result]
    for i, d in enumerate(devices):
        if not d.iridium_number:
            continue
        lp_result = MagicMock()
        lp_id = last_point_ids[i] if last_point_ids and i < len(last_point_ids) else None
        lp_result.scalar_one_or_none.return_value = lp_id
        side.append(lp_result)

    # 3. Duplicate check — одна фабрика на все оставшиеся execute()
    dup_result = MagicMock()
    dup_result.scalar_one_or_none.return_value = existing_point_id

    def _execute_side(*args, **kwargs):
        return side.pop(0) if side else dup_result

    session.execute.side_effect = _execute_side
    return session


def _patch_session_factory(session, monkeypatch):
    """Мокает фабрику сессий для Celery-задач."""

    @asynccontextmanager
    async def _mock_session_factory():
        yield session

    # Подменяем функцию получения фабрики в модуле задачи
    monkeypatch.setattr(
        "app.tasks.tracking.get_celery_session_factory", lambda: _mock_session_factory
    )


def _mock_client(*positions) -> AsyncMock:
    client = AsyncMock()
    client.fetch_positions.return_value = list(positions)
    return client


def _point(
    iridium_number: str = "001",
    point_id: str = "abc-123",
    battery: int | None = 80,
) -> MagicMock:
    return MagicMock(
        iridium_number=iridium_number,
        iridium_point_id=point_id,
        lat=55.0,
        lon=37.0,
        recorded_at=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
        course_deg=45.0,
        speed_kmh=10.0,
        altitude_m=850.0,
        battery_percent=battery,
    )


class TestPollIridium:
    """poll_iridium — опрос Iridium360."""

    @pytest.mark.asyncio
    async def test_saves_points(self, monkeypatch) -> None:
        """Новые точки сохраняются в TrackPoint."""
        from app.tasks.tracking import _poll_iridium

        device = _make_device()
        session = _make_session([device], last_point_ids=[None], existing_point_id=None)
        _patch_session_factory(session, monkeypatch)

        mock_client = _mock_client(_point())

        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            result = await _poll_iridium()

        assert result == {"devices": 1, "ingested": 1, "duplicated": 0}

        added = [c[0][0] for c in session.add.call_args_list]
        track_points = [x for x in added if isinstance(x, TrackPoint)]
        assert len(track_points) == 1
        tp = track_points[0]
        assert tp.device_id == device.id
        assert tp.participant_id == device.participant_id
        assert tp.stage_id == device.stage_id
        assert tp.lat == 55.0
        assert tp.lon == 37.0
        assert tp.altitude == 850.0
        assert tp.course_deg == 45.0
        assert tp.source_speed == 10.0
        assert tp.iridium_point_id == "abc-123"
        assert tp.is_confirmed is True

        # обновление device
        assert device.last_message_at == datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        assert device.battery_percent == 80

    @pytest.mark.asyncio
    async def test_calculates_speed_and_route_progress_in_recorded_order(self, monkeypatch) -> None:
        from app.tasks.tracking import _poll_iridium

        device = _make_device()
        session = _make_session([device])
        _patch_session_factory(session, monkeypatch)

        earlier = _point(point_id="earlier")
        earlier.lon = 37.0
        later = _point(point_id="later")
        later.lon = 37.01
        later.recorded_at = datetime(2024, 1, 15, 10, 40, tzinfo=UTC)
        client = _mock_client(later, earlier)

        route = [
            StageRoutePoint(stage_id=1, position=0, lat=55.0, lon=37.0),
            StageRoutePoint(stage_id=1, position=1, lat=55.0, lon=37.02),
        ]
        with (
            patch("app.tasks.tracking.get_iridium_client", return_value=client),
            patch(
                "app.services.tracking_metrics.StageRoutePointRepository.list_for_stage",
                new_callable=AsyncMock,
                return_value=route,
            ),
        ):
            result = await _poll_iridium()

        saved = [
            call.args[0]
            for call in session.add.call_args_list
            if isinstance(call.args[0], TrackPoint)
        ]
        assert result == {"devices": 1, "ingested": 2, "duplicated": 0}
        assert [point.iridium_point_id for point in saved] == ["earlier", "later"]
        assert saved[0].average_speed_kmh is None
        assert saved[1].average_speed_kmh == pytest.approx(3.827, rel=0.01)
        assert saved[0].km_from_start == pytest.approx(0.0)
        assert saved[1].km_from_start == pytest.approx(0.638, rel=0.01)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deduplication_by_point_id(self, monkeypatch) -> None:
        """Точка, для которой deduplication_key уже есть в БД → duplicated=1."""
        from app.tasks.tracking import _poll_iridium

        device = _make_device()
        session = _make_session([device], last_point_ids=[None], existing_point_id=42)
        _patch_session_factory(session, monkeypatch)

        mock_client = _mock_client(_point(point_id="abc-123"))

        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            result = await _poll_iridium()

        assert result == {"devices": 1, "ingested": 0, "duplicated": 1}
        added = [c[0][0] for c in session.add.call_args_list]
        assert not [x for x in added if isinstance(x, TrackPoint)]

    @pytest.mark.asyncio
    async def test_deduplication_fallback_sha256(self, monkeypatch) -> None:
        """Без iridium_point_id — дедупликация по sha256."""
        from app.tasks.tracking import _poll_iridium

        device = _make_device()
        session = _make_session([device], last_point_ids=[None], existing_point_id=42)
        _patch_session_factory(session, monkeypatch)

        point = _point(point_id="")  # пустой point_id
        mock_client = _mock_client(point)

        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            result = await _poll_iridium()

        assert result == {"devices": 1, "ingested": 0, "duplicated": 1}

    @pytest.mark.asyncio
    async def test_no_active_devices(self, monkeypatch) -> None:
        """Нет активных устройств → devices=0, без вызова клиента."""
        from app.tasks.tracking import _poll_iridium

        session = _make_session([])
        _patch_session_factory(session, monkeypatch)

        mock_client = AsyncMock()
        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            result = await _poll_iridium()

        assert result == {"devices": 0, "ingested": 0, "duplicated": 0}
        mock_client.fetch_positions.assert_not_called()

    @pytest.mark.asyncio
    async def test_number_not_matched(self, monkeypatch) -> None:
        """Позиция для неизвестного iridium_number → игнорируется."""
        from app.tasks.tracking import _poll_iridium

        device = _make_device(iridium_number="001")
        session = _make_session([device], last_point_ids=[None], existing_point_id=None)
        _patch_session_factory(session, monkeypatch)

        mock_client = _mock_client(_point(iridium_number="999"))

        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            result = await _poll_iridium()

        assert result == {"devices": 1, "ingested": 0, "duplicated": 0}

    @pytest.mark.asyncio
    async def test_last_point_id_passed_to_client(self, monkeypatch) -> None:
        """Последний iridium_point_id из БД передаётся в fetch_positions."""
        from app.tasks.tracking import _poll_iridium

        device = _make_device(iridium_number="001")
        # last_point_id = "abc-100"
        session = _make_session([device], last_point_ids=["abc-100"], existing_point_id=None)
        _patch_session_factory(session, monkeypatch)

        mock_client = AsyncMock()
        mock_client.fetch_positions.return_value = []

        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            await _poll_iridium()

        # Проверяем, что fetch_positions вызван с правильным last_point_id
        mock_client.fetch_positions.assert_called_once()
        args = mock_client.fetch_positions.call_args[0][0]
        assert len(args) == 1
        assert args[0] == ("001", "abc-100")

    @pytest.mark.asyncio
    async def test_no_iridium_number(self, monkeypatch) -> None:
        """Device без iridium_number → пропускается."""
        from app.tasks.tracking import _poll_iridium

        device = _make_device(iridium_number="")
        session = _make_session([device])
        _patch_session_factory(session, monkeypatch)

        mock_client = AsyncMock()

        with patch("app.tasks.tracking.get_iridium_client", return_value=mock_client):
            result = await _poll_iridium()

        assert result == {"devices": 0, "ingested": 0, "duplicated": 0}
        mock_client.fetch_positions.assert_not_called()
