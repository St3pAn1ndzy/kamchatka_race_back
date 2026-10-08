"""Репозиторий этапов гонки"""

from sqlalchemy import select

from app.db.models.stage import Stage
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
        """Возращаем список (с условием/без условия сезона) этапов"""
        stmt = select(Stage)
        if season_id is not None:
            stmt = stmt.where(Stage.season_id == season_id)
        stmt = stmt.order_by(Stage.order_index, Stage.number, Stage.id)
        return list((await self.session.execute(stmt)).scalars().all())
