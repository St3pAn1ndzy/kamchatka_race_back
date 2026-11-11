from sqlalchemy import select

from app.db.models.discipline import Discipline
from app.repositories.base import BaseRepository


class DisciplineRepository(BaseRepository[Discipline]):
    model = Discipline

    async def get_by_season_and_code(self, season_id: int, code: str) -> Discipline | None:
        """Возращаем конкретную дисциплину по сезону и названию (в разных сезонах могут быть один-ые названия)"""
        stmt = select(Discipline).where(
            Discipline.season_id == season_id,
            Discipline.code == code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_ordered(
        self,
        *,
        season_id: int | None = None,
        include_inactive: bool = True,
    ) -> list[Discipline]:
        """Просто возращаем список дисциплин по сезону"""
        stmt = select(Discipline)
        if season_id is not None:
            stmt = stmt.where(Discipline.season_id == season_id)
        if not include_inactive:
            stmt = stmt.where(Discipline.is_active.is_(True))
        stmt = stmt.order_by(Discipline.season_id, Discipline.sort_order, Discipline.name)
        return list((await self.session.execute(stmt)).scalars().all())
