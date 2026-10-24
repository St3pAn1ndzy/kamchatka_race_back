"""Репозиторий подписок «Болею за»."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, func, select

from app.db.models.fun_subscription import FanSubscription
from app.repositories.base import BaseRepository


class FanSubscriptionRepository(BaseRepository[FanSubscription]):
    model = FanSubscription

    async def add(self, user_id: int, participant_id: int) -> bool:
        """Подписать. True — создано, False — уже было (идемпотентно)."""
        existing = await self.is_fan(user_id, participant_id)
        if existing:
            return False
        self.session.add(FanSubscription(user_id=user_id, participant_id=participant_id))
        await self.session.flush()
        return True

    async def remove(self, user_id: int, participant_id: int) -> bool:
        """Отписать. True — удалено, False — не было."""
        stmt = (
            delete(FanSubscription)
            .where(
                FanSubscription.user_id == user_id,
                FanSubscription.participant_id == participant_id,
            )
            .returning(FanSubscription.id)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def is_fan(self, user_id: int, participant_id: int) -> bool:
        """Болеет ли пользователь за участника."""
        stmt = select(FanSubscription.id).where(
            FanSubscription.user_id == user_id,
            FanSubscription.participant_id == participant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def count_by_participant(self, participant_id: int) -> int:
        """Число болельщиков участника."""
        stmt = select(func.count(FanSubscription.id)).where(
            FanSubscription.participant_id == participant_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def delta_24h(self, participant_id: int) -> int:
        """Прирост болельщиков за последние 24 часа."""
        since = datetime.now(tz=UTC) - timedelta(hours=24)
        stmt = select(func.count(FanSubscription.id)).where(
            FanSubscription.participant_id == participant_id,
            FanSubscription.created_at >= since,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def list_participant_ids_by_user(self, user_id: int) -> list[int]:
        """ID участников, за которых болеет пользователь."""
        stmt = select(FanSubscription.participant_id).where(FanSubscription.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def rating(self, *, limit: int = 50) -> list[tuple[int, int]]:
        """Топ участников по числу болельщиков: [(participant_id, cnt), ...]."""
        stmt = (
            select(
                FanSubscription.participant_id,
                func.count(FanSubscription.id).label("cnt"),
            )
            .group_by(FanSubscription.participant_id)
            .order_by(desc("cnt"), FanSubscription.participant_id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(int(pid), int(cnt)) for pid, cnt in result.all()]
