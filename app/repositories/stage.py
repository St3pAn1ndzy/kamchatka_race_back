"""Репозиторий этапов гонки"""

from datetime import datetime

from sqlalchemy import select

from app.db.models.stage import Stage
from app.enums import StageStatus
from app.repositories.base import BaseRepository


class StageRepository(BaseRepository[Stage]):
    """Запросы к этапам гонки"""

    model = Stage

    async def get_by_season_and_number(self, season_id: int, number: int) -> Stage | None:
        stmt = select(Stage).where(Stage.season_id == season_id, Stage.number == number)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def exists_by_id(self, stage_id: int) -> bool:
        """Проверить, что этап существует"""
        stmt = select(Stage.id).where(Stage.id == stage_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def list_ordered(self, *, season_id: int | None = None) -> list[Stage]:
        """Возвращаем список (с условием/без условия сезона) этапов"""
        stmt = select(Stage)
        if season_id is not None:
            stmt = stmt.where(Stage.season_id == season_id)
        stmt = stmt.order_by(Stage.order_index, Stage.number, Stage.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_update(self, stage_id: int) -> Stage | None:
        stmt = select(Stage).where(Stage.id == stage_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_active_for_season(self, season_id: int) -> Stage | None:
        """Этап со status=ACTIVE в сезоне. None если такого нет."""
        stmt = (
            select(Stage)
            .where(
                Stage.season_id == season_id,
                Stage.status == StageStatus.ACTIVE.value,
            )
            .order_by(Stage.order_index)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_current_by_time(self, season_id: int, now: datetime) -> Stage | None:
        """Этап, в интервал [start_time, finish_time] которого попадает `now`."""
        stmt = (
            select(Stage)
            .where(
                Stage.season_id == season_id,
                Stage.start_time <= now,
                Stage.finish_time >= now,
            )
            .order_by(Stage.order_index)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
