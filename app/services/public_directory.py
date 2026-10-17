"""Публичный сервис справочников гонки."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.discipline import Discipline
from app.db.models.season import Season
from app.db.models.stage import Stage
from app.repositories.discipline import DisciplineRepository
from app.repositories.season import SeasonRepository
from app.repositories.stage import StageRepository


class PublicDirectoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.seasons = SeasonRepository(session)
        self.disciplines = DisciplineRepository(session)
        self.stages = StageRepository(session)

    async def get_active_season(self) -> Season | None:
        """Активный сезон. None, если ни один не помечен is_active=True."""
        return await self.seasons.get_active()

    async def list_disciplines(
        self,
        *,
        season_id: int | None = None,
    ) -> list[Discipline]:
        """Активные дисциплины. По умолчанию — активного сезона."""
        if season_id is None:
            season = await self.get_active_season()
            if season is None:
                return []
            season_id = season.id

        return await self.disciplines.list_ordered(
            season_id=season_id,
            include_inactive=False,
        )

    async def list_stages(
        self,
        *,
        season_id: int | None = None,
    ) -> list[Stage]:
        """Этапы сезона, отсортированы по order_index. По умолчанию — активного сезона."""
        if season_id is None:
            season = await self.get_active_season()
            if season is None:
                return []
            season_id = season.id

        return await self.stages.list_ordered(season_id=season_id)
