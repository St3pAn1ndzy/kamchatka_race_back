import math
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint
from app.repositories.stage_route_point import StageRoutePointRepository
from app.repositories.track_point import TrackPointRepository

EARTH_RADIUS_KM = 6371.0088
MAX_ROUTE_OFFSET_KM = 1.0


def _longitude_delta(start: float, end: float) -> float:
    return (end - start + 180) % 360 - 180


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    lat_delta = math.radians(lat_b - lat_a)
    lon_delta = math.radians(_longitude_delta(lon_a, lon_b))
    arc = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(lon_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(arc)))


def route_progress_km(
    route: Sequence[StageRoutePoint],
    lat: float,
    lon: float,
) -> float | None:
    if len(route) < 2:
        return None

    nearest_offset = math.inf
    nearest_progress = 0.0
    distance_before_segment = 0.0

    for start, end in zip(route, route[1:], strict=False):
        segment_km = _distance_km(start.lat, start.lon, end.lat, end.lon)
        mean_lat = math.radians((start.lat + end.lat) / 2)
        dx = math.radians(_longitude_delta(start.lon, end.lon)) * math.cos(mean_lat)
        dy = math.radians(end.lat - start.lat)
        px = math.radians(_longitude_delta(start.lon, lon)) * math.cos(mean_lat)
        py = math.radians(lat - start.lat)
        segment_squared = dx * dx + dy * dy
        if segment_squared == 0:
            distance_before_segment += segment_km
            continue

        fraction = max(0.0, min(1.0, (px * dx + py * dy) / segment_squared))
        offset_km = math.hypot(px - fraction * dx, py - fraction * dy) * EARTH_RADIUS_KM
        if offset_km < nearest_offset:
            nearest_offset = offset_km
            nearest_progress = distance_before_segment + fraction * segment_km
        distance_before_segment += segment_km

    if nearest_offset > MAX_ROUTE_OFFSET_KM:
        return None
    return nearest_progress


class TrackingMetricsService:
    def __init__(self, session: AsyncSession) -> None:
        self.track_points = TrackPointRepository(session)
        self.routes = StageRoutePointRepository(session)
        self._last_points: dict[tuple[int, int | None, int | None], TrackPoint | None] = {}
        self._routes_by_stage: dict[int, list[StageRoutePoint]] = {}

    async def fill_metrics(self, point: TrackPoint) -> None:
        key = (point.device_id, point.stage_id, point.participant_id)
        if key not in self._last_points:
            self._last_points[key] = await self.track_points.latest_for_assignment(*key)
        previous = self._last_points[key]

        # Запоздавшая точка не должна менять уже рассчитанный прогресс
        if previous is not None and point.recorded_at <= previous.recorded_at:
            return

        if previous is not None:
            seconds = (point.recorded_at - previous.recorded_at).total_seconds()
            distance = _distance_km(previous.lat, previous.lon, point.lat, point.lon)
            point.average_speed_kmh = distance * 3600 / seconds

        if point.stage_id is not None:
            if point.stage_id not in self._routes_by_stage:
                self._routes_by_stage[point.stage_id] = await self.routes.list_for_stage(
                    point.stage_id
                )
            progress = route_progress_km(
                self._routes_by_stage[point.stage_id], point.lat, point.lon
            )
            previous_progress = previous.km_from_start if previous is not None else None
            if progress is not None:
                point.km_from_start = max(progress, previous_progress or 0.0)
            else:
                point.km_from_start = previous_progress

        self._last_points[key] = point
