"""Метрики для дашборда админ-панели.

Только чтение. Все запросы собраны в одном месте, чтобы view оставался тонким.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import TrackPoint
from app.db.models.audit_log import AuditLog
from app.db.models.device import Device
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.race_status import RaceStatus
from app.db.models.season import Season
from app.db.models.stage import Stage
from app.enums import ParticipantStatus, PublicationStatus, RaceState, StageStatus


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


@dataclass(frozen=True)
class StageTimelineItem:
    """Короткая карточка этапа для таймлайна на дашборде."""

    id: int
    number: int
    name: str
    start_time: datetime | None
    status: str


@dataclass(frozen=True)
class RaceModeInfo:
    """Текущий режим гонки и активный этап."""

    status: str
    current_stage_number: int | None
    current_stage_name: str | None


@dataclass(frozen=True)
class ActivityItem:
    """Запись журнала для блока «Последние действия»."""

    action: str
    entity_type: str
    entity_id: str | None
    admin_login: str | None
    created_at: datetime


@dataclass(frozen=True)
class AttentionDevice:
    """Трекер, требующий внимания (SOS, потеря связи, низкий заряд)."""

    device_id: int
    iridium_number: str
    device_name: str
    participant_number: int | None
    participant_name: str | None
    reason: str  # sos | stale | low_battery | never_seen
    last_message_at: datetime | None
    battery_percent: int | None


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

    async def get_stages_timeline(self) -> list[StageTimelineItem]:
        """Этапы активного сезона для горизонтального таймлайна."""
        active_season = await self._get_active_season()
        season_id = active_season.id if active_season else None

        stmt = select(Stage).order_by(Stage.order_index, Stage.number)
        if season_id is not None:
            stmt = stmt.where(Stage.season_id == season_id)

        stages = (await self.session.execute(stmt)).scalars().all()
        return [
            StageTimelineItem(
                id=stage.id,
                number=stage.number,
                name=stage.name,
                start_time=stage.start_time,
                status=stage.status,
            )
            for stage in stages
        ]

    async def get_race_mode(self) -> RaceModeInfo:
        """Текущий режим гонки из RaceStatus."""
        stmt = (
            select(RaceStatus)
            .options(selectinload(RaceStatus.current_stage))
            .order_by(RaceStatus.updated_at.desc())
            .limit(1)
        )
        race_status = (await self.session.execute(stmt)).scalar_one_or_none()

        if race_status is None:
            return RaceModeInfo(
                status=RaceState.UPCOMING.value,
                current_stage_number=None,
                current_stage_name=None,
            )

        stage = race_status.current_stage
        return RaceModeInfo(
            status=race_status.status,
            current_stage_number=stage.number if stage else None,
            current_stage_name=stage.name if stage else None,
        )

    async def get_recent_activity(self, limit: int = 6) -> list[ActivityItem]:
        """Последние действия администраторов из журнала."""
        stmt = (
            select(AuditLog)
            .options(selectinload(AuditLog.admin))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        logs = (await self.session.execute(stmt)).scalars().all()

        return [
            ActivityItem(
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                admin_login=log.admin.login if log.admin else None,
                created_at=log.created_at,
            )
            for log in logs
        ]

    async def get_attention_devices(self, limit: int = 5) -> list[AttentionDevice]:
        """Трекеры, требующие внимания: SOS, потеря связи, низкий заряд."""
        now = datetime.now(tz=UTC)
        stale_interval_minutes = (
            self.settings.TRACKING_POLL_INTERVAL_SECONDS
            * self.settings.TRACKING_STALE_MISSED_INTERVALS
        ) // 60
        stale_before = now - timedelta(minutes=stale_interval_minutes)

        stmt = (
            select(Device)
            .options(selectinload(Device.participant))
            .where(
                Device.is_active.is_(True),
                or_(
                    Device.sos_active.is_(True),
                    Device.last_message_at.is_(None),
                    Device.last_message_at < stale_before,
                    Device.battery_percent <= 20,
                ),
            )
            .order_by(
                Device.sos_active.desc(),
                Device.last_message_at.asc().nullsfirst(),
            )
            .limit(limit)
        )
        devices = (await self.session.execute(stmt)).scalars().all()

        def _reason(device: Device) -> str:
            if device.sos_active:
                return "sos"
            if device.last_message_at is None:
                return "never_seen"
            if device.last_message_at < stale_before:
                return "stale"
            if device.battery_percent is not None and device.battery_percent <= 20:
                return "low_battery"
            return "stale"

        return [
            AttentionDevice(
                device_id=device.id,
                iridium_number=device.iridium_number,
                device_name=device.name,
                participant_number=(device.participant.number if device.participant else None),
                participant_name=device.participant.name if device.participant else None,
                reason=_reason(device),
                last_message_at=device.last_message_at,
                battery_percent=device.battery_percent,
            )
            for device in devices
        ]

    # --- Внутренние хелперы -------------------------------------------------

    async def get_map_data(self) -> dict:
        """Данные для мини-карты: участники, маршрут, КП."""
        from app.db.models.checkpoint import Checkpoint
        from app.db.models.stage_route_point import StageRoutePoint
        from app.db.models.track_point import TrackPoint

        race = await self.get_race_mode()
        active_stage_id = None
        if race.current_stage_number:
            stmt = select(Stage).where(Stage.number == race.current_stage_number)
            stage = (await self.session.execute(stmt)).scalar_one_or_none()
            if stage:
                active_stage_id = stage.id

        # Участники с последней точкой
        subq = select(
            TrackPoint.device_id,
            TrackPoint.lat,
            TrackPoint.lon,
            func.row_number()
            .over(partition_by=TrackPoint.device_id, order_by=TrackPoint.recorded_at.desc())
            .label("rn"),
        ).subquery()
        stmt = (
            select(Device, Participant, subq.c.lat, subq.c.lon)
            .join(Participant, Device.participant_id == Participant.id, isouter=True)
            .outerjoin(subq, (subq.c.device_id == Device.id) & (subq.c.rn == 1))
            .where(Device.is_active.is_(True))
        )
        rows = (await self.session.execute(stmt)).all()
        participants = [
            {
                "number": p.number if p else None,
                "name": p.name if p else None,
                "lat": lat,
                "lon": lon,
                "sos": d.sos_active,
            }
            for d, p, lat, lon in rows
        ]

        # Маршрут активного этапа
        route = []
        if active_stage_id:
            rp_stmt = (
                select(StageRoutePoint)
                .where(StageRoutePoint.stage_id == active_stage_id)
                .order_by(StageRoutePoint.position)
            )
            points = (await self.session.execute(rp_stmt)).scalars().all()
            route = [{"lat": p.lat, "lon": p.lon} for p in points]

        # КП активного этапа
        checkpoints = []
        if active_stage_id:
            cp_stmt = (
                select(Checkpoint)
                .where(Checkpoint.stage_id == active_stage_id)
                .order_by(Checkpoint.order_index)
            )
            cps = (await self.session.execute(cp_stmt)).scalars().all()
            checkpoints = [
                {"code": cp.code, "name": cp.name, "lat": cp.lat, "lon": cp.lon, "kind": cp.kind}
                for cp in cps
            ]

        return {"participants": participants, "route": route, "checkpoints": checkpoints}

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
