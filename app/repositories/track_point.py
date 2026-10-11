from sqlalchemy import select

from app.db.models.track_point import TrackPoint
from app.repositories.base import BaseRepository


class TrackPointRepository(BaseRepository[TrackPoint]):
    model = TrackPoint

    async def exists_for_stage(self, stage_id: int) -> bool:
        stmt = select(TrackPoint.id).where(TrackPoint.stage_id == stage_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
