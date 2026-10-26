"""Публичный сервис справочников гонки."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.season import Season
from app.repositories.discipline import DisciplineRepository
from app.repositories.season import SeasonRepository
from app.repositories.stage import StageRepository
from app.schemas.public_directory import (
    DisciplinePublicResponse,
    StagePublicResponse,
)
from app.services.cache import cache


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
    ) -> list[DisciplinePublicResponse] | None:
        """Активные дисциплины. По умолчанию — активного сезона.

        Возвращает None, если season_id не передан и активного сезона нет.
        Возвращает [] если сезон есть, но в нём нет активных дисциплин.
        Результат кэшируется на 1 час для активного сезона.
        """
        use_cache = season_id is None

        if use_cache:
            cached = await cache.get("public:disciplines:active")
            if cached is not None:
                return [DisciplinePublicResponse(**item) for item in cached]

        if season_id is None:
            season = await self.get_active_season()
            if season is None:
                return None
            season_id = season.id

        disciplines = await self.disciplines.list_ordered(
            season_id=season_id,
            include_inactive=False,
        )
        result = [DisciplinePublicResponse.model_validate(d) for d in disciplines]

        if use_cache:
            settings = get_settings()
            await cache.set(
                "public:disciplines:active",
                [r.model_dump(mode="json") for r in result],
                settings.CACHE_TTL_STAGES,
            )

        return result

    async def list_stages(
        self,
        *,
        season_id: int | None = None,
    ) -> list[StagePublicResponse] | None:
        """Этапы сезона, отсортированы по order_index. По умолчанию — активного сезона.

        Возвращает None, если season_id не передан и активного сезона нет.
        Возвращает [] если сезон есть, но в нём нет этапов.
        Результат кэшируется на 1 час для активного сезона.
        """
        use_cache = season_id is None

        if use_cache:
            cached = await cache.get("public:stages:active")
            if cached is not None:
                return [StagePublicResponse(**item) for item in cached]

        if season_id is None:
            season = await self.get_active_season()
            if season is None:
                return None
            season_id = season.id

        stages = await self.stages.list_ordered(season_id=season_id)
        result = [StagePublicResponse.model_validate(s) for s in stages]

        if use_cache:
            settings = get_settings()
            await cache.set(
                "public:stages:active",
                [r.model_dump(mode="json") for r in result],
                settings.CACHE_TTL_STAGES,
            )

        return result

    async def get_active_stage(self) -> StagePublicResponse | None:
        """Текущий активный этап сезона.

        Приоритет:
        1. Этап со status=ACTIVE в активном сезоне.
        2. Иначе — этап, в чей интервал [start_time, finish_time] попадает `now`.
        3. Если ничего не нашли — None (роутер отдаст 404).
        """
        season = await self.get_active_season()
        if season is None:
            return None

        stage = await self.stages.get_active_for_season(season.id)
        if stage is None:
            stage = await self.stages.get_current_by_time(season.id, datetime.now(tz=UTC))

        if stage is None:
            return None

        return StagePublicResponse.model_validate(stage)
