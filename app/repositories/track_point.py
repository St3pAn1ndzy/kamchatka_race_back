from sqlalchemy import select

from app.db.models.track_point import TrackPoint
from app.repositories.base import BaseRepository


class TrackPointRepository(BaseRepository[TrackPoint]):
    model = TrackPoint

    async def latest_for_assignment(
        self, device_id: int, stage_id: int | None, participant_id: int | None
    ) -> TrackPoint | None:
        stmt = select(TrackPoint).where(TrackPoint.device_id == device_id)
        stmt = stmt.where(
            TrackPoint.stage_id == stage_id
            if stage_id is not None
            else TrackPoint.stage_id.is_(None)
        )
        stmt = stmt.where(
            TrackPoint.participant_id == participant_id
            if participant_id is not None
            else TrackPoint.participant_id.is_(None)
        )
        stmt = stmt.order_by(TrackPoint.recorded_at.desc(), TrackPoint.id.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def exists_for_stage(self, stage_id: int) -> bool:
        stmt = select(TrackPoint.id).where(TrackPoint.stage_id == stage_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
