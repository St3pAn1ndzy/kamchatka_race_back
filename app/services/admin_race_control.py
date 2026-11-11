"""Сервис для экрана оперативного штаба гонки (Race Control)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_panel.formatters import map_freshness_to_color
from app.config import get_settings
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.db.models.track_point import TrackPoint
from app.enums import ParticipantStatus, StageStatus
from app.repositories import DeviceRepository
from app.services.tracking_freshness import get_freshness_status


@dataclass
class RaceControlRow:
    position: int
    participant_id: int
    number: int
    name: str
    region: str | None
    km_from_start: float
    average_speed_kmh: float | None
    last_seen_minutes: int | None
    progress_percent: float
    status_color: str  # success | warning | danger
    freshness_status: str
    sos_active: bool = False
    sos_device_id: int | None = None


@dataclass
class RaceControlState:
    stage_name: str | None
    stage_distance: float | None
    rows: list[RaceControlRow]


class AdminRaceControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.device_repo = DeviceRepository(session)

    async def get_race_states(self) -> list[RaceControlState]:
        """Возвращает состояние гонки для ВСЕХ активных этапов."""
        now = datetime.now(tz=UTC)

        # 1. Ищем ВСЕ активные этапы
        stages_stmt = (
            select(Stage).where(Stage.status == StageStatus.ACTIVE.value).order_by(Stage.number)
        )
        active_stages = (await self.session.execute(stages_stmt)).scalars().all()

        if not active_stages:
            return []

        # 2. Берем всех активных участников (они общие для всех этапов)
        participants_stmt = select(Participant).where(
            Participant.status == ParticipantStatus.ACTIVE.value
        )
        participants = (await self.session.execute(participants_stmt)).scalars().all()

        if not participants:
            # Если нет участников, возвращаем пустые таблицы для активных этапов
            return [
                RaceControlState(stage_name=s.name, stage_distance=s.distance_km, rows=[])
                for s in active_stages
            ]

        participant_ids = [p.id for p in participants]

        # ═══ Получаем маппинг participant_id -> device_id для SOS ═══
        sos_device_map = await self.device_repo.get_sos_device_mapping(participant_ids)

        states = []

        # 3. Проходимся по каждому активному этапу
        for stage in active_stages:
            # Интервал именно этого этапа
            interval_seconds = (
                stage.tracker_interval_seconds
                if stage.tracker_interval_seconds
                else self.settings.TRACKING_POLL_INTERVAL_SECONDS
            )
            # Достаем последнюю точку трека для каждого участника ИМЕННО НА ЭТОМ ЭТАПЕ
            latest_points_sq = (
                select(
                    TrackPoint.participant_id,
                    TrackPoint.km_from_start,
                    TrackPoint.average_speed_kmh,
                    TrackPoint.recorded_at,
                    func.row_number()
                    .over(
                        partition_by=TrackPoint.participant_id,
                        order_by=TrackPoint.recorded_at.desc(),
                    )
                    .label("rn"),
                )
                .where(
                    TrackPoint.stage_id == stage.id,  # Фильтр по конкретному этапу
                    TrackPoint.participant_id.in_(participant_ids),
                )
                .subquery()
            )

            points_stmt = select(latest_points_sq).where(latest_points_sq.c.rn == 1)
            points_result = (await self.session.execute(points_stmt)).all()

            points_map = {
                row.participant_id: (
                    row.km_from_start or 0.0,
                    row.average_speed_kmh,
                    row.recorded_at,
                )
                for row in points_result
            }

            rows = []
            for p in participants:
                km, speed, recorded_at = points_map.get(p.id, (0.0, None, None))

                last_seen_minutes = None
                if recorded_at:
                    last_seen_minutes = int((now - recorded_at).total_seconds() / 60)

                freshness = get_freshness_status(
                    last_message_at=recorded_at,
                    now=now,
                    interval_seconds=interval_seconds,
                    stale_missed_intervals=self.settings.TRACKING_STALE_MISSED_INTERVALS,
                )

                color = map_freshness_to_color(freshness)

                progress = 0.0
                if stage.distance_km and stage.distance_km > 0:
                    progress = min(100.0, max(0.0, (km / stage.distance_km) * 100))

                rows.append(
                    RaceControlRow(
                        position=0,
                        participant_id=p.id,
                        number=p.number,
                        name=p.name,
                        region=p.region,
                        km_from_start=km,
                        average_speed_kmh=speed,
                        last_seen_minutes=last_seen_minutes,
                        progress_percent=progress,
                        status_color=color,
                        freshness_status=freshness,
                        sos_active=p.id in sos_device_map,
                        sos_device_id=sos_device_map.get(p.id),
                    )
                )

            # Сортируем и присваиваем места
            rows.sort(key=lambda r: r.km_from_start, reverse=True)
            for idx, row in enumerate(rows, start=1):
                row.position = idx

            states.append(
                RaceControlState(
                    stage_name=stage.name,
                    stage_distance=stage.distance_km,
                    rows=rows,
                )
            )

        return states
