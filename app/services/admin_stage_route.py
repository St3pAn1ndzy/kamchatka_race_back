from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.checkpoint import Checkpoint
from app.db.models.stage_route_point import StageRoutePoint
from app.repositories.stage import StageRepository
from app.repositories.stage_route_point import StageRoutePointRepository
from app.repositories.track_point import TrackPointRepository
from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.cache import cache
from app.services.route_distances import lock_route_seasons, update_route_distances
from app.services.tracking_metrics import _distance_km, reproject_latest_points, route_progress_km


class AdminStageRouteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.stages = StageRepository(session)
        self.routes = StageRoutePointRepository(session)
        self.track_points = TrackPointRepository(session)

    async def get_route(self, stage_id: int) -> list[StageRoutePoint]:
        if not await self.stages.exists_by_id(stage_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")
        return await self.routes.list_for_stage(stage_id)

    async def replace_route(
        self,
        stage_id: int,
        body: StageRouteReplaceRequest,
        *,
        admin_id: int,
    ) -> list[StageRoutePoint]:
        coordinates = [(point.lat, point.lon) for point in body.points]
        return await self._save_route(stage_id, coordinates, admin_id=admin_id)

    async def clear_route(self, stage_id: int, *, admin_id: int) -> None:
        await self._save_route(stage_id, [], admin_id=admin_id)

    async def _save_route(
        self,
        stage_id: int,
        coordinates: list[tuple[float, float]],
        *,
        admin_id: int,
    ) -> list[StageRoutePoint]:
        # Блокируем этап, чтобы две админские замены не пересеклись
        await lock_route_seasons(self.session, [stage_id])
        stage = await self.stages.get_for_update(stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")

        old_points = await self.routes.list_for_stage(stage_id)
        old_coordinates = [(point.lat, point.lon) for point in old_points]
        if old_coordinates == coordinates:
            # Маршрут не изменился, завершаем транзакцию и освобождаем блокировку этапа
            await self.session.commit()
            return old_points

        has_history = await self.track_points.exists_for_stage(stage_id)
        if stage.status == "finished" or (has_history and not coordinates):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Нельзя менять завершённый этап или очищать маршрут с GPS-историей",
            )

        distance, projected = None, []
        if coordinates:
            geometry = [SimpleNamespace(lat=lat, lon=lon) for lat, lon in coordinates]
            distance = sum(
                _distance_km(a.lat, a.lon, b.lat, b.lon)
                for a, b in zip(geometry, geometry[1:], strict=False)
            )
            checkpoints = await self.session.scalars(
                select(Checkpoint)
                .where(Checkpoint.stage_id == stage_id)
                .order_by(Checkpoint.id)
                .with_for_update()
            )
            for cp in checkpoints:
                km = route_progress_km(geometry, cp.lat, cp.lon)
                if km is None:
                    raise HTTPException(
                        409, "КП находится вне новой линии: используйте импорт маршрута с КП"
                    )
                if cp.kind in {"start", "finish"}:
                    endpoint = geometry[0] if cp.kind == "start" else geometry[-1]
                    if _distance_km(cp.lat, cp.lon, endpoint.lat, endpoint.lon) > 0.2:
                        raise HTTPException(
                            409, "Старт или финиш перемещён: используйте импорт маршрута с КП"
                        )
                    km = 0.0 if cp.kind == "start" else distance
                projected.append((cp, km))
        try:
            saved = await self.routes.replace_for_stage(stage_id, coordinates)
            if distance is not None:
                offsets = await update_route_distances(self.session, [stage], {stage_id: distance})
                ordered = sorted(
                    projected, key=lambda item: (item[1], item[0].order_index, item[0].id)
                )
                for index, (cp, km) in enumerate(ordered):
                    cp.km_from_race_start = offsets[stage_id] + km
                    cp.order_index = index
            if has_history:
                await reproject_latest_points(self.session, stage_id, saved)
            self.session.add(
                AuditLog(
                    admin_id=admin_id,
                    action="stage_route_cleared" if not coordinates else "stage_route_replaced",
                    entity_type="stage",
                    entity_id=str(stage_id),
                    payload={
                        "old": [{"lat": lat, "lon": lon} for lat, lon in old_coordinates],
                        "new": [{"lat": lat, "lon": lon} for lat, lon in coordinates],
                    },
                )
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Данные маршрута изменились, повторите импорт") from exc
        await cache.invalidate_pattern("public:map:*")
        await cache.invalidate_pattern("public:stages:*")
        await cache.invalidate_pattern("admin:*")
        return saved
