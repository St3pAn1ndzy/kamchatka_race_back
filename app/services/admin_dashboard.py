"""Метрики для дашборда админ-панели.

Только чтение. Все запросы собраны в одном месте, чтобы view оставался тонким.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import TrackPoint
from app.db.models.device import Device
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.season import Season
from app.db.models.stage import Stage
from app.enums import ParticipantStatus, PublicationStatus, StageStatus


@dataclass(frozen=True)
class DashboardStats:
    """Снимок метрик для дашборда."""

    participants_total: int
    participants_active: int
    participants_finished: int
    stages_total: int
    stages_active: int
    stages_draft_results: int
    marks_today: int
    marks_total: int
    devices_total: int
    devices_online: int
    devices_stale: int
    devices_sos: int


@dataclass(frozen=True)
class SosDevice:
    """Активный SOS-сигнал по трекеру."""

    device_id: int
    iridium_number: str
    device_name: str
    participant_id: int | None
    participant_number: int | None
    participant_name: str | None
    stage_number: int | None
    last_message_at: datetime | None
    lat: float | None
    lon: float | None


class AdminDashboardService:
    """Собирает метрики для дашборда."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def get_stats(self) -> DashboardStats:

        now = datetime.now(tz=UTC)
        stale_interval_minutes = (
            self.settings.TRACKING_POLL_INTERVAL_SECONDS
            * self.settings.TRACKING_STALE_MISSED_INTERVALS
        ) // 60
        stale_before = now - timedelta(minutes=stale_interval_minutes)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        active_season = await self._get_active_season()
        season_id = active_season.id if active_season else None

        return DashboardStats(
            participants_total=await self._count(Participant),
            participants_active=await self._count(
                Participant, Participant.status == ParticipantStatus.ACTIVE.value
            ),
            participants_finished=await self._count(
                Participant, Participant.status == ParticipantStatus.FINISHED.value
            ),
            stages_total=await self._count(Stage, self._season_filter(Stage, season_id)),
            stages_active=await self._count(
                Stage,
                self._season_filter(Stage, season_id),
                Stage.status == StageStatus.ACTIVE.value,
            ),
            stages_draft_results=await self._count(
                Stage,
                self._season_filter(Stage, season_id),
                Stage.results_publication == PublicationStatus.DRAFT.value,
            ),
            marks_today=await self._count(OfficialMark, OfficialMark.created_at >= today_start),
            marks_total=await self._count(OfficialMark),
            devices_total=await self._count(Device),
            devices_online=await self._count(
                Device,
                Device.is_active.is_(True),
                Device.last_message_at >= stale_before,
            ),
            devices_stale=await self._count(
                Device,
                Device.is_active.is_(True),
                Device.last_message_at < stale_before,
            ),
            devices_sos=await self._count(Device, Device.sos_active.is_(True)),
        )

    async def get_sos_devices(self) -> list[SosDevice]:
        """Активные SOS-сигналы.

        Позиция берётся из последней подтверждённой точки трека.
        Если трек пуст — координаты None.
        """
        # Подзапрос: последний track_point для каждого device.
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
            select(
                Device,
                Participant,
                Stage,
                latest_point_sq.c.lat,
                latest_point_sq.c.lon,
            )
            .outerjoin(Participant, Device.participant_id == Participant.id)
            .outerjoin(Stage, Device.stage_id == Stage.id)
            .outerjoin(
                latest_point_sq,
                (latest_point_sq.c.device_id == Device.id) & (latest_point_sq.c.rn == 1),
            )
            .where(Device.sos_active.is_(True))
            .order_by(Device.last_message_at.desc().nullslast())
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            SosDevice(
                device_id=device.id,
                iridium_number=device.iridium_number,
                device_name=device.name,
                participant_id=participant.id if participant else None,
                participant_number=participant.number if participant else None,
                participant_name=participant.name if participant else None,
                stage_number=stage.number if stage else None,
                last_message_at=device.last_message_at,
                lat=lat,
                lon=lon,
            )
            for device, participant, stage, lat, lon in rows
        ]

    # --- Внутренние хелперы -------------------------------------------------

    async def _get_active_season(self) -> Season | None:
        stmt = (
            select(Season).where(Season.is_active.is_(True)).order_by(Season.year.desc()).limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _season_filter(model, season_id: int | None):
        """Фильтр по сезону. Если сезон не задан — фильтр всегда True."""
        if season_id is None:
            return model.id.is_not(None)  # placeholder, не влияет на COUNT
        return model.season_id == season_id

    async def _count(self, model, *conditions) -> int:
        stmt = select(func.count(model.id))
        for cond in conditions:
            stmt = stmt.where(cond)
        return (await self.session.execute(stmt)).scalar_one()
