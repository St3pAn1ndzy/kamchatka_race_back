from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint
from app.services.tracking_metrics import TrackingMetricsService, route_progress_km


def _route() -> list[StageRoutePoint]:
    return [
        StageRoutePoint(stage_id=1, position=0, lat=0.0, lon=0.0),
        StageRoutePoint(stage_id=1, position=1, lat=0.0, lon=0.02),
    ]


def _point(lon: float, minute: int, *, stage_id: int | None = 1) -> TrackPoint:
    return TrackPoint(
        device_id=1,
        participant_id=2,
        stage_id=stage_id,
        lat=0.0,
        lon=lon,
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
    )


def test_project_position_onto_route() -> None:
    progress = route_progress_km(_route(), 0.001, 0.01)
    assert progress == pytest.approx(1.11195, rel=0.01)


def test_ignore_position_far_from_route() -> None:
    assert route_progress_km(_route(), 0.02, 0.01) is None


def test_route_needs_two_points() -> None:
    assert route_progress_km(_route()[:1], 0.0, 0.01) is None


@pytest.mark.asyncio
async def test_metrics_use_route_progress_and_keep_maximum() -> None:
    service = TrackingMetricsService(AsyncMock())
    service.track_points.latest_for_assignment = AsyncMock(return_value=None)
    service.routes.list_for_stage = AsyncMock(return_value=_route())

    first = _point(0.005, 0)
    forward = _point(0.015, 10)
    backward = _point(0.01, 20)
    await service.fill_metrics(first)
    await service.fill_metrics(forward)
    await service.fill_metrics(backward)

    assert first.average_speed_kmh is None
    assert first.km_from_start == pytest.approx(0.556, rel=0.01)
    assert forward.km_from_start == pytest.approx(1.668, rel=0.01)
    assert forward.average_speed_kmh == pytest.approx(6.672, rel=0.01)
    assert backward.km_from_start == forward.km_from_start
    service.track_points.latest_for_assignment.assert_awaited_once_with(1, 1, 2)
    service.routes.list_for_stage.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_late_point_does_not_replace_latest_metrics() -> None:
    previous = _point(0.015, 10)
    previous.km_from_start = 1.5
    service = TrackingMetricsService(AsyncMock())
    service.track_points.latest_for_assignment = AsyncMock(return_value=previous)
    service.routes.list_for_stage = AsyncMock(return_value=_route())

    late = _point(0.005, 5)
    newer = _point(0.018, 20)
    await service.fill_metrics(late)
    await service.fill_metrics(newer)

    assert late.km_from_start is None
    assert late.average_speed_kmh is None
    assert newer.km_from_start == pytest.approx(2.002, rel=0.01)
    assert newer.average_speed_kmh == pytest.approx(2.002, rel=0.01)


@pytest.mark.asyncio
async def test_missing_route_keeps_progress_empty_but_calculates_speed() -> None:
    previous = _point(0.005, 0, stage_id=None)
    service = TrackingMetricsService(AsyncMock())
    service.track_points.latest_for_assignment = AsyncMock(return_value=previous)
    service.routes.list_for_stage = AsyncMock()

    current = _point(0.01, 10, stage_id=None)
    await service.fill_metrics(current)

    assert current.km_from_start is None
    assert current.average_speed_kmh == pytest.approx(3.336, rel=0.01)
    service.routes.list_for_stage.assert_not_awaited()


@pytest.mark.asyncio
async def test_off_route_point_preserves_previous_progress() -> None:
    previous = _point(0.005, 0)
    previous.km_from_start = 0.55
    service = TrackingMetricsService(AsyncMock())
    service.track_points.latest_for_assignment = AsyncMock(return_value=previous)
    service.routes.list_for_stage = AsyncMock(return_value=_route())

    current = _point(0.01, 10)
    current.lat = 0.02
    await service.fill_metrics(current)

    assert current.km_from_start == 0.55
