"""Репозиторий этапов гонки"""

from sqlalchemy import select

from app.db.models.stage import Stage
from app.repositories.base import BaseRepository


class StageRepository(BaseRepository[Stage]):
    """Запросы к этапам гонки"""

    model = Stage

    async def exists_by_id(self, stage_id: int) -> bool:
        """Проверить, что этап существует"""
        stmt = select(Stage.id).where(Stage.id == stage_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
