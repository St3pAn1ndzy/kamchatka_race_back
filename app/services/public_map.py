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
        cache_key = f"{_PREFIX_CHECKPOINT}{stage_id}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return MapCheckpointsResponse(**cached)

        await self._stage(stage_id)
        checkpoints = await self.checkpoints.list_public_for_stage(stage_id)

        items = [
            MapCheckpoint(
                id=cp.id,
                code=cp.code,
                name=cp.name,
                type=cp.kind,  # маппинг kind -> type
                description=cp.description,
                lat=cp.lat,
                lon=cp.lon,
                elevation=cp.altitude,  # маппинг altitude -> elevation
                km=cp.km_from_race_start,  # маппинг km_from_race_start -> km
                order_index=cp.order_index,
            )
            for cp in checkpoints
        ]

        result = MapCheckpointsResponse(stage_id=stage_id, items=items)
        await cache.set(cache_key, result.model_dump(mode="json"), self.settings.CACHE_TTL_MAP)
        return result

    async def get_stage_route_geojson(self, stage_id: int) -> dict:
        """Возвращает GeoJSON LineString (нитку всего маршрута этапа)."""
        cache_key = f"public:map:route:{stage_id}"
        if cached := await cache.get(cache_key):
            return cached

        await self._stage(stage_id)

        # Берем точки маршрута из БД

        points = await self.route_points.list_for_stage(stage_id)

        # Формируем GeoJSON (lon, lat)
        coordinates = [[p.lon, p.lat] for p in points]

        result = {"type": "LineString", "coordinates": coordinates}

        # Кэшируем надолго (трасса не меняется)
        await cache.set(cache_key, result, self.settings.CACHE_TTL_STAGES)
        return result

    async def get_positions(self, stage_id: int, since: datetime | None = None) -> list[dict]:
        """Последние координаты участников + last_cp_id для карты."""
        cache_key = f"public:map:positions:{stage_id}"

        # Кэшируем только если нет фильтра since
        if not since and (cached := await cache.get(cache_key)):
            return cached

        # 1. Получаем всех участников с их последними координатами и freshness
        participants_resp = await self.get_participants(stage_id, limit=1000, offset=0)

        # 2. Достаем все отметки этапа.

        marks = await self.marks.get_for_stage(stage_id)

        # 3. Собираем словарь {participant_id: last_checkpoint_id}
        # Так как список отсортирован по времени, последняя запись для каждого
        # участника и будет его последним пройденным КП.
        last_cp_map: dict[int, int] = {}
        for mark in marks:
            last_cp_map[mark.participant_id] = mark.checkpoint_id

        # 4. Формируем итоговый ответ
        result = []
        for item in participants_resp.items:
            if not item.position:
                continue  # Пропускаем, если нет GPS-данных

            # Фильтр по времени, если передан since
            if since and item.position.recorded_at <= since:
                continue

            result.append(
                {
                    "participant_id": item.id,
                    "bib": item.number,
                    "lat": item.position.lat,
                    "lon": item.position.lon,
                    "recorded_at": item.position.recorded_at,
                    "source": "iridium",
                    "last_cp_id": last_cp_map.get(item.id),
                    "freshness": item.freshness_status,
                }
            )

        # 5. Сохраняем в кэш
        if not since:
            await cache.set(cache_key, result, self.settings.CACHE_TTL_MAP)

        return result

    async def get_leaders(
        self, stage_id: int, discipline: str | None = None, as_of: datetime | None = None
    ) -> dict:
        """Рейтинг лидеров на основе судейских отметок."""
        cache_key = f"public:map:leaders:{stage_id}:{discipline or 'all'}:{as_of or 'now'}"
        if cached := await cache.get(cache_key):
            return cached

        await self._stage(stage_id)

        # Получаем все активные отметки на этапе
        marks = await self.marks.get_for_stage(stage_id)

        # Фильтруем по времени, если передан as_of
        if as_of:
            marks = [m for m in marks if m.mark_time <= as_of]

        # Группируем по участнику
        participant_marks: dict[int, list] = {}
        for m in marks:
            if m.participant_id not in participant_marks:
                participant_marks[m.participant_id] = []
            participant_marks[m.participant_id].append(m)

        if not participant_marks:
            return {"as_of": as_of or datetime.now(tz=UTC), "leaders": []}

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

            # Сортируем отметки по порядку КП (order_index)
            p_marks.sort(key=lambda x: x.checkpoint.order_index)

            # Последний пройденный КП
            last_mark = p_marks[-1]

            leaders_data.append(
                {
                    "participant_id": participant.id,
                    "bib": participant.number,
                    "last_cp_order": last_mark.checkpoint.order_index,
                    "last_mark_time": last_mark.mark_time,
                    "name": participant.name,
                }
            )

        # Сортируем лидеров: сначала те, кто прошел больше КП (order_index),
        # при равенстве — кто прошел последний КП раньше.
        leaders_data.sort(key=lambda x: (-x["last_cp_order"], x["last_mark_time"]))

        # Присваиваем места
        now = datetime.now(tz=UTC)
        result = {
            "as_of": as_of or now,
            "leaders": [
                {"participant_id": item["participant_id"], "bib": item["bib"], "place": index + 1}
                for index, item in enumerate(leaders_data)
            ],
        }

        await cache.set(cache_key, result, self.settings.CACHE_TTL_MAP)
        return result
