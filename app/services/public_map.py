from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.stage import Stage
from app.repositories import OfficialMarkRepository
from app.repositories.checkpoint import CheckpointRepository
from app.repositories.discipline import DisciplineRepository
from app.repositories.participant import ParticipantRepository
from app.repositories.stage import StageRepository
from app.repositories.stage_route_point import StageRoutePointRepository
from app.repositories.track_point import TrackPointRepository
from app.schemas.map import (
    MapParticipant,
    MapParticipantsResponse,
    MapPosition,
    MapTrackResponse,
)
from app.schemas.public_stages import (
    CheckpointPublicResponse,
    LeaderRow,
    LeadersResponse,
    PositionPublicResponse,
    StageTrackResponse,
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
        self.route_points = StageRoutePointRepository(session)
        self.marks = OfficialMarkRepository(session)
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
                    stage_id=stage_id,
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

    async def get_checkpoints(self, stage_id: int) -> list[CheckpointPublicResponse]:
        cache_key = f"{_PREFIX_CHECKPOINT}{stage_id}"
        if cached := await cache.get(cache_key):
            return [CheckpointPublicResponse(**item) for item in cached]

        await self._stage(stage_id)
        checkpoints = await self.checkpoints.list_public_for_stage(stage_id)

        items = [
            CheckpointPublicResponse(
                id=cp.id,
                code=cp.code,
                name=cp.name,
                type=cp.kind,
                description=cp.description,
                lat=cp.lat,
                lon=cp.lon,
                elevation=cp.altitude,
                km=cp.km_from_race_start,
                order_index=cp.order_index,
            )
            for cp in checkpoints
        ]
        await cache.set(
            cache_key, [i.model_dump(mode="json") for i in items], self.settings.CACHE_TTL_MAP
        )
        return items

    async def get_stage_route_geojson(self, stage_id: int) -> StageTrackResponse | None:
        """GeoJSON нитка маршрута этапа.

        Возвращает None, если маршрут не загружен (роутер отдаст 404).
        """
        cache_key = f"public:map:route:{stage_id}"

        if (cached := await cache.get(cache_key)) and cached.get("coordinates"):
            return StageTrackResponse(**cached)

        await self._stage(stage_id)

        # Берем точки маршрута из БД
        points = await self.route_points.list_for_stage(stage_id)

        if not points:
            return None

        coordinates = [[p.lon, p.lat] for p in points]
        result = StageTrackResponse(coordinates=coordinates)
        await cache.set(cache_key, result.model_dump(mode="json"), self.settings.CACHE_TTL_STAGES)
        return result

    async def get_positions(
        self, stage_id: int, since: datetime | None = None
    ) -> list[PositionPublicResponse]:
        cache_key = f"public:map:positions:{stage_id}"
        if not since and (cached := await cache.get(cache_key)):
            return [PositionPublicResponse(**item) for item in cached]

        participants_resp = await self.get_participants(stage_id, limit=1000, offset=0)
        marks = await self.marks.get_for_stage(stage_id)

        last_cp_map = {mark.participant_id: mark.checkpoint_id for mark in marks}

        result = []
        for item in participants_resp.items:
            if not item.position:
                continue
            if since and item.position.recorded_at <= since:
                continue

            result.append(
                PositionPublicResponse(
                    participant_id=item.id,
                    bib=item.number,
                    lat=item.position.lat,
                    lon=item.position.lon,
                    recorded_at=item.position.recorded_at,
                    source="iridium",
                    last_cp_id=last_cp_map.get(item.id),
                    freshness=item.freshness_status,
                )
            )

        if not since:
            await cache.set(
                cache_key, [i.model_dump(mode="json") for i in result], self.settings.CACHE_TTL_MAP
            )

        return result

    async def get_leaders(
        self, stage_id: int, discipline: str | None = None, as_of: datetime | None = None
    ) -> LeadersResponse:
        cache_key = f"public:map:leaders:{stage_id}:{discipline or 'all'}:{as_of or 'now'}"
        if cached := await cache.get(cache_key):
            return LeadersResponse(**cached)

        await self._stage(stage_id)
        marks = await self.marks.get_for_stage(stage_id)

        if as_of:
            marks = [m for m in marks if m.mark_time <= as_of]

        participant_marks: dict[int, list] = {}
        for m in marks:
            if m.participant_id not in participant_marks:
                participant_marks[m.participant_id] = []
            participant_marks[m.participant_id].append(m)

        now = datetime.now(tz=UTC)

        if not participant_marks:
            return LeadersResponse(as_of=as_of or now, leaders=[])

        p_ids = list(participant_marks.keys())
        participants = await self.participants.get_many_with_disciplines(p_ids)
        participants_map = {p.id: p for p in participants}

        leaders_data = []
        for p_id, p_marks in participant_marks.items():
            participant = participants_map.get(p_id)
            if not participant:
                continue

            if (
                discipline
                and participant.discipline_ref
                and participant.discipline_ref.code != discipline
            ):
                continue

            p_marks.sort(key=lambda x: x.checkpoint.order_index)
            last_mark = p_marks[-1]

            leaders_data.append(
                {
                    "participant_id": participant.id,
                    "bib": participant.number,
                    "last_cp_order": last_mark.checkpoint.order_index,
                    "last_mark_time": last_mark.mark_time,
                }
            )

        leaders_data.sort(key=lambda x: (-x["last_cp_order"], x["last_mark_time"]))

        result = LeadersResponse(
            as_of=as_of or now,
            leaders=[
                LeaderRow(participant_id=item["participant_id"], bib=item["bib"], place=index + 1)
                for index, item in enumerate(leaders_data)
            ],
        )

        await cache.set(cache_key, result.model_dump(mode="json"), self.settings.CACHE_TTL_MAP)
        return result
