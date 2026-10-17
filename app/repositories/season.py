from sqlalchemy import select

from app.db.models.season import Season
from app.repositories.base import BaseRepository


class SeasonRepository(BaseRepository[Season]):
    model = Season

    async def get_by_year(self, year: int) -> Season | None:
        """Возращаем сезон по году"""
        stmt = select(Season).where(Season.year == year)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_ordered(self) -> list[Season]:
        """Возращаем список сезонов"""
        stmt = select(Season).order_by(Season.year.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_active(self) -> Season | None:
        """Активный сезон. None, если ни один не помечен is_active=True."""
        stmt = (
            select(Season).where(Season.is_active.is_(True)).order_by(Season.year.desc()).limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
