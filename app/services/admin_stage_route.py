from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.stage_route_point import StageRoutePoint
from app.repositories.stage import StageRepository
from app.repositories.stage_route_point import StageRoutePointRepository
from app.repositories.track_point import TrackPointRepository
from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.cache import cache


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
        if await self.stages.get_for_update(stage_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")

        old_points = await self.routes.list_for_stage(stage_id)
        old_coordinates = [(point.lat, point.lon) for point in old_points]
        if old_coordinates == coordinates:
            # Маршрут не изменился, завершаем транзакцию и освобождаем блокировку этапа
            await self.session.commit()
            return old_points

        if await self.track_points.exists_for_stage(stage_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Маршрут нельзя менять после появления трек-точек этапа",
            )

        saved = await self.routes.replace_for_stage(stage_id, coordinates)
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
        await cache.delete(f"public:map:route:{stage_id}")
        return saved
