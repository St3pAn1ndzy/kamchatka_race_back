"""Метрики для дашборда админ-панели.

Только чтение. Все запросы собраны в одном месте, чтобы view оставался тонким.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models.audit_log import AuditLog
from app.db.models.device import Device
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.season import Season
from app.db.models.stage import Stage
from app.enums import ParticipantStatus, PublicationStatus, RaceState, StageStatus
from app.repositories import DeviceRepository, RaceStatusRepository, StageRepository
from app.repositories.checkpoint import CheckpointRepository
from app.repositories.stage_route_point import StageRoutePointRepository
from app.services.cache import cache


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
        self.stage_repo = StageRepository(session)
        self.route_repo = StageRoutePointRepository(session)
        self.checkpoint_repo = CheckpointRepository(session)
        self.race_status_repo = RaceStatusRepository(session)
        self.device_repo = DeviceRepository(session)

    async def get_stats(self) -> DashboardStats:
        """Снимок метрик для дашборда. Кэшируется на 30 секунд."""
        cached = await cache.get("admin:dashboard:stats")
        if cached is not None:
            return DashboardStats(**cached)

        now = datetime.now(tz=UTC)
        stale_interval_minutes = (
            self.settings.TRACKING_POLL_INTERVAL_SECONDS
            * self.settings.TRACKING_STALE_MISSED_INTERVALS
        ) // 60
        stale_before = now - timedelta(minutes=stale_interval_minutes)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        active_season = await self._get_active_season()
        season_id = active_season.id if active_season else None

        stats = DashboardStats(
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

        # Сохраняем в кэш на 30 секунд
        await cache.set(
            "admin:dashboard:stats",
            asdict(stats),
            ttl=self.settings.CACHE_TTL_STATS,
        )

        return stats

    async def get_sos_devices(self) -> list[SosDevice]:
        """Активные SOS-сигналы."""
        positions = await self.device_repo.list_active_with_positions(only_sos=True)
        return [
            SosDevice(
                device_id=pos.device_id,
                iridium_number=pos.iridium_number,
                device_name=pos.device_name,
                participant_id=pos.participant_id,
                participant_number=pos.participant_number,
                participant_name=pos.participant_name,
                stage_number=pos.stage_number,
                last_message_at=pos.last_message_at,
                lat=pos.lat,
                lon=pos.lon,
            )
            for pos in positions
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
        race_status = await self.race_status_repo.get_current()

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
        """Данные для мини-карты: маршрут активного этапа, КП, позиции участников."""
        active_stage = await self._resolve_active_stage()

        route: list[dict] = []
        checkpoints: list[dict] = []

        if active_stage is not None:
            route_points = await self.route_repo.list_for_stage(active_stage.id)
            route = [{"lat": p.lat, "lon": p.lon} for p in route_points]

            cps = await self.checkpoint_repo.list_public_for_stage(active_stage.id)
            checkpoints = [
                {
                    "code": cp.code,
                    "name": cp.name,
                    "lat": cp.lat,
                    "lon": cp.lon,
                    "kind": cp.kind,
                }
                for cp in cps
            ]

        positions = await self.device_repo.list_active_with_positions()
        participants = [
            {
                "number": pos.participant_number,
                "name": pos.participant_name,
                "lat": pos.lat,
                "lon": pos.lon,
                "sos": pos.sos_active,
            }
            for pos in positions
            if pos.lat is not None and pos.lon is not None
        ]

        return {
            "participants": participants,
            "route": route,
            "checkpoints": checkpoints,
        }

    async def _resolve_active_stage(self) -> Stage | None:
        """Активный этап: RaceStatus → ACTIVE в сезоне → первый по порядку."""
        race_status = await self.race_status_repo.get_current()
        if race_status is not None and race_status.current_stage is not None:
            return race_status.current_stage

        season = await self._get_active_season()
        if season is None:
            return None

        stage = await self.stage_repo.get_active_for_season(season.id)
        if stage is not None:
            return stage

        stages = await self.stage_repo.list_ordered(season_id=season.id)
        return stages[0] if stages else None

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
