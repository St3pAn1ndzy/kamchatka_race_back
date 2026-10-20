"""Read-only сервис для экрана «Статистика»."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fun_subscription import FanSubscription
from app.db.models.participant import Participant
from app.db.models.track_point import TrackPoint


@dataclass
class TopFanItem:
    participant_number: int
    participant_name: str
    fans_count: int


@dataclass
class StatsOverview:
    total_fans: int
    total_participants: int
    total_track_points: int
    top_fans: list[TopFanItem]


class AdminStatisticsService:
    """Статистика для админ-панели."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stats(self) -> StatsOverview:
        total_fans = (
            await self.session.execute(select(func.count(FanSubscription.id)))
        ).scalar() or 0
        total_participants = (
            await self.session.execute(select(func.count(Participant.id)))
        ).scalar() or 0
        total_track_points = (
            await self.session.execute(select(func.count(TrackPoint.id)))
        ).scalar() or 0

        # Топ-10 по фанатам
        top_stmt = (
            select(
                Participant.number,
                Participant.name,
                func.count(FanSubscription.id).label("cnt"),
            )
            .join(FanSubscription, FanSubscription.participant_id == Participant.id)
            .group_by(Participant.id, Participant.number, Participant.name)
            .order_by(func.count(FanSubscription.id).desc())
            .limit(10)
        )
        top_rows = (await self.session.execute(top_stmt)).all()

        top_fans = [
            TopFanItem(participant_number=row.number, participant_name=row.name, fans_count=row.cnt)
            for row in top_rows
        ]

        return StatsOverview(
            total_fans=total_fans,
            total_participants=total_participants,
            total_track_points=total_track_points,
            top_fans=top_fans,
        )
