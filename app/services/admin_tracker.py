"""Сервис для экрана мониторинга трекеров."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_panel.formatters import map_freshness_to_color
from app.config import get_settings
from app.db.models import Stage
from app.db.models.device import Device
from app.db.models.participant import Participant
from app.db.models.track_point import TrackPoint
from app.services.tracking_freshness import get_freshness_status


@dataclass
class TrackerStatus:
    device_id: int
    iridium: str
    name: str
    participant_name: str | None
    battery: int | None
    sos_active: bool
    last_seen_minutes: int | None
    lat: float | None
    lon: float | None
    status_color: str  # success | warning | danger
    freshness_status: str


class AdminTrackerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def get_trackers(self) -> list[TrackerStatus]:
        now = datetime.now(tz=UTC)

        # Подзапрос: последняя точка для каждого устройства (координаты)
        latest_point_sq = select(
            TrackPoint.device_id,
            TrackPoint.lat,
            TrackPoint.lon,
            func.row_number()
            .over(
                partition_by=TrackPoint.device_id,
                order_by=TrackPoint.recorded_at.desc(),
            )
            .label("rn"),
        ).subquery()

        stmt = (
            select(Device, Participant, Stage, latest_point_sq.c.lat, latest_point_sq.c.lon)
            .outerjoin(Participant, Device.participant_id == Participant.id)
            .outerjoin(Stage, Device.stage_id == Stage.id)  # Добавили Stage
            .outerjoin(
                latest_point_sq,
                (latest_point_sq.c.device_id == Device.id) & (latest_point_sq.c.rn == 1),
            )
            .where(Device.is_active.is_(True))
            .order_by(Device.iridium_number)
        )

        rows = (await self.session.execute(stmt)).all()
        result = []

        for device, participant, stage, lat, lon in rows:
            # Используем интервал этапа, если он есть. Иначе — дефолтный из настроек
            interval_seconds = (
                stage.tracker_interval_seconds
                if stage and stage.tracker_interval_seconds
                else self.settings.TRACKING_POLL_INTERVAL_SECONDS
            )

            # Вызываем твой сервис
            freshness = get_freshness_status(
                last_message_at=device.last_message_at,
                now=now,
                interval_seconds=interval_seconds,
                stale_missed_intervals=self.settings.TRACKING_STALE_MISSED_INTERVALS,
            )

            last_seen_minutes = None
            if device.last_message_at:
                last_seen_minutes = int((now - device.last_message_at).total_seconds() / 60)

            color = map_freshness_to_color(freshness)

            result.append(
                TrackerStatus(
                    device_id=device.id,
                    iridium=device.iridium_number,
                    name=device.name,
                    participant_name=(
                        f"№{participant.number} {participant.name}" if participant else None
                    ),
                    battery=device.battery_percent,
                    sos_active=device.sos_active,
                    last_seen_minutes=last_seen_minutes,
                    lat=lat,
                    lon=lon,
                    status_color="danger" if device.sos_active else color,  # SOS всегда красный
                    freshness_status=freshness,
                )
            )

        return result
