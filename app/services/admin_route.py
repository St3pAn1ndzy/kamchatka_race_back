"""Read-only сервис для экрана «Гонка и маршрут»."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.checkpoint import Checkpoint
from app.db.models.stage import Stage
from app.db.models.stage_route_point import StageRoutePoint


@dataclass
class RouteStageInfo:
    id: int
    number: int
    name: str
    distance_km: float
    status: str
    route_points_count: int
    checkpoints: list = field(default_factory=list)
    route_points: list = field(default_factory=list)


class AdminRouteService:
    """Данные для экрана «Гонка и маршрут»."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stages(self) -> list[RouteStageInfo]:
        stmt = (
            select(Stage)
            .options(selectinload(Stage.route_points), selectinload(Stage.checkpoints))
            .order_by(Stage.number)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        result = []
        for s in rows:
            cps = [
                {"code": cp.code, "name": cp.name, "lat": cp.lat, "lon": cp.lon, "kind": cp.kind}
                for cp in s.checkpoints
            ]
            rps = [{"lat": rp.lat, "lon": rp.lon} for rp in s.route_points]
            result.append(
                RouteStageInfo(
                    id=s.id,
                    number=s.number,
                    name=s.name,
                    distance_km=s.distance_km,
                    status=s.status,
                    route_points_count=len(s.route_points),
                    checkpoints=cps,
                    route_points=rps,
                )
            )
        return result

    async def get_route_by_stage(self, stage_id: int) -> list[dict]:
        stmt = (
            select(StageRoutePoint)
            .where(StageRoutePoint.stage_id == stage_id)
            .order_by(StageRoutePoint.position)
        )
        points = (await self.session.execute(stmt)).scalars().all()
        return [{"lat": p.lat, "lon": p.lon} for p in points]

    async def get_checkpoints_by_stage(self, stage_id: int) -> list[dict]:
        stmt = (
            select(Checkpoint)
            .where(Checkpoint.stage_id == stage_id)
            .order_by(Checkpoint.order_index)
        )
        cps = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "code": cp.code,
                "name": cp.name,
                "lat": cp.lat,
                "lon": cp.lon,
                "kind": cp.kind,
            }
            for cp in cps
        ]
