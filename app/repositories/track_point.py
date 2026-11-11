from sqlalchemy import func, select

from app.db.models.track_point import TrackPoint
from app.repositories.base import BaseRepository


class TrackPointRepository(BaseRepository[TrackPoint]):
    model = TrackPoint

    async def participant_ids_for_stage(self, stage_id: int) -> list[int]:
        stmt = (
            select(TrackPoint.participant_id)
            .where(
                TrackPoint.stage_id == stage_id,
                TrackPoint.participant_id.is_not(None),
                TrackPoint.is_confirmed.is_(True),
            )
            .distinct()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest_for_map(self, stage_id: int, participant_ids: list[int]) -> list[TrackPoint]:
        if not participant_ids:
            return []
        ranked = (
            select(
                TrackPoint.id.label("point_id"),
                func.row_number()
                .over(
                    partition_by=TrackPoint.participant_id,
                    order_by=(TrackPoint.recorded_at.desc(), TrackPoint.id.desc()),
                )
                .label("rank"),
            )
            .where(
                TrackPoint.stage_id == stage_id,
                TrackPoint.participant_id.in_(participant_ids),
                TrackPoint.is_confirmed.is_(True),
            )
            .subquery()
        )
        stmt = (
            select(TrackPoint)
            .join(ranked, TrackPoint.id == ranked.c.point_id)
            .where(ranked.c.rank == 1)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_map_track(
        self, stage_id: int, participant_id: int, *, limit: int, offset: int
    ) -> tuple[list[TrackPoint], int]:
        filters = (
            TrackPoint.stage_id == stage_id,
            TrackPoint.participant_id == participant_id,
            TrackPoint.is_confirmed.is_(True),
        )
        total = int(
            (
                await self.session.execute(select(func.count(TrackPoint.id)).where(*filters))
            ).scalar_one()
        )
        stmt = (
            select(TrackPoint)
            .where(*filters)
            .order_by(TrackPoint.recorded_at, TrackPoint.id)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

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
