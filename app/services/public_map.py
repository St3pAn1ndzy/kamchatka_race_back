from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.stage import Stage
from app.repositories.checkpoint import CheckpointRepository
from app.repositories.discipline import DisciplineRepository
from app.repositories.participant import ParticipantRepository
from app.repositories.stage import StageRepository
from app.repositories.track_point import TrackPointRepository
from app.schemas.map import (
    MapCheckpoint,
    MapCheckpointsResponse,
    MapParticipant,
    MapParticipantsResponse,
    MapPosition,
    MapTrackResponse,
)
from app.services.cache import cache
from app.services.tracking_freshness import get_freshness_status

_PREFIX_MODEL = "public:map:model:"
_PREFIX_CHECKPOINT = "public:map:checkpoint:"


class PublicMapService:
    def __init__(self, session: AsyncSession) -> None:
        self.stages = StageRepository(session)
        self.disciplines = DisciplineRepository(session)
        self.participants = ParticipantRepository(session)
        self.track_points = TrackPointRepository(session)
        self.checkpoints = CheckpointRepository(session)
        self.settings = get_settings()

    async def _stage(self, stage_id: int) -> Stage:
        stage = await self.stages.get_by_id(stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")
        return stage

    async def get_participants(
        self, stage_id: int, *, limit: int, offset: int
    ) -> MapParticipantsResponse:
        # Попытка достать из кэша
        cache_key = f"{_PREFIX_MODEL}{stage_id}:{limit}:{offset}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return MapParticipantsResponse(**cached)

        stage = await self._stage(stage_id)
        if stage.season_id is not None:
            disciplines = await self.disciplines.list_ordered(season_id=stage.season_id)
            discipline_ids = [discipline.id for discipline in disciplines]
            participant_ids = None
        else:
            discipline_ids = None
            participant_ids = await self.track_points.participant_ids_for_stage(stage_id)

        participants, total = await self.participants.list_for_map(
            discipline_ids=discipline_ids,
            participant_ids=participant_ids,
            limit=limit,
            offset=offset,
        )
        points = await self.track_points.latest_for_map(
            stage_id, [participant.id for participant in participants]
        )
        latest_by_participant = {point.participant_id: point for point in points}
        interval = (
            stage.tracker_interval_seconds
            if stage.tracker_interval_seconds > 0
            else self.settings.TRACKING_POLL_INTERVAL_SECONDS
        )
        now = datetime.now(tz=UTC)

        items = []
        for participant in participants:
            point = latest_by_participant.get(participant.id)
            freshness = get_freshness_status(
                point.recorded_at if point else None,
                now=now,
                interval_seconds=interval,
                stale_missed_intervals=self.settings.TRACKING_STALE_MISSED_INTERVALS,
            )
            items.append(
                MapParticipant(
                    id=participant.id,
                    number=participant.number,
                    name=participant.name,
                    discipline_id=participant.discipline_id,
                    discipline=(
                        participant.discipline_ref.name if participant.discipline_ref else None
                    ),
                    status=participant.status,
                    freshness_status="no_data" if freshness == "no_signal" else freshness,
                    position=MapPosition.model_validate(point) if point else None,
                )
            )
        result = MapParticipantsResponse(
            stage_id=stage_id, items=items, total=total, limit=limit, offset=offset
        )
        # Сохраняем в кэш
        await cache.set(cache_key, result.model_dump(mode="json"), self.settings.CACHE_TTL_MAP)
        return result

    async def get_track(
        self, stage_id: int, participant_id: int, *, limit: int, offset: int
    ) -> MapTrackResponse:
        # Попытка достать из кэша
        cache_key = f"public:map:track:{stage_id}:{participant_id}:{limit}:{offset}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return MapTrackResponse(**cached)

        stage = await self._stage(stage_id)
        participant = await self.participants.get_by_id(participant_id)
        if participant is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")
        if stage.season_id is not None:
            discipline = (
                await self.disciplines.get_by_id(participant.discipline_id)
                if participant.discipline_id is not None
                else None
            )
            if discipline is None or discipline.season_id != stage.season_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден на этапе")

        points, total = await self.track_points.list_for_map_track(
            stage_id, participant_id, limit=limit, offset=offset
        )
        if stage.season_id is None and total == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден на этапе")
        result = MapTrackResponse(
            stage_id=stage_id,
            participant_id=participant_id,
            points=[MapPosition.model_validate(point) for point in points],
            total=total,
            limit=limit,
            offset=offset,
        )
        # Сохраняем в кэш
        await cache.set(cache_key, result.model_dump(mode="json"), self.settings.CACHE_TTL_MAP)
        return result

    async def get_checkpoints(self, stage_id: int) -> MapCheckpointsResponse:
        # Попытка достать из кэша
        cache_key = f"{_PREFIX_CHECKPOINT}{stage_id}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return MapCheckpointsResponse(**cached)

        await self._stage(stage_id)
        checkpoints = await self.checkpoints.list_public_for_stage(stage_id)
        result = MapCheckpointsResponse(
            stage_id=stage_id,
            items=[MapCheckpoint.model_validate(checkpoint) for checkpoint in checkpoints],
        )
        # Сохраняем в кэш
        await cache.set(cache_key, result.model_dump(mode="json"), self.settings.CACHE_TTL_MAP)
        return result
