from sqlalchemy import delete, select

from app.db.models.stage_route_point import StageRoutePoint
from app.repositories.base import BaseRepository


class StageRoutePointRepository(BaseRepository[StageRoutePoint]):
    model = StageRoutePoint

    async def list_for_stage(self, stage_id: int) -> list[StageRoutePoint]:
        stmt = (
            select(StageRoutePoint)
            .where(StageRoutePoint.stage_id == stage_id)
            .order_by(StageRoutePoint.position)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def replace_for_stage(
        self,
        stage_id: int,
        coordinates: list[tuple[float, float]],
    ) -> list[StageRoutePoint]:
        await self.session.execute(
            delete(StageRoutePoint).where(StageRoutePoint.stage_id == stage_id)
        )
        points = [
            StageRoutePoint(stage_id=stage_id, position=index, lat=lat, lon=lon)
            for index, (lat, lon) in enumerate(coordinates)
        ]
        self.session.add_all(points)
        await self.session.flush()
        return points
