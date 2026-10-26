"""Репозиторий зрительских локаций."""

from sqlalchemy import case, select

from app.db.models.viewer_location import ViewerLocation
from app.enums import ViewerLocationKind
from app.repositories.base import BaseRepository


class ViewerLocationRepository(BaseRepository[ViewerLocation]):
    model = ViewerLocation

    async def list_public(
        self,
        *,
        kind: ViewerLocationKind | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ViewerLocation]:
        """Публичные локации с сортировкой по типу и имени."""
        kind_order = case(
            (ViewerLocation.kind == ViewerLocationKind.START.value, 0),
            (ViewerLocation.kind == ViewerLocationKind.FINISH.value, 1),
            (ViewerLocation.kind == ViewerLocationKind.VIEWPOINT.value, 2),
            (ViewerLocation.kind == ViewerLocationKind.FESTIVAL.value, 3),
            else_=4,
        )
        stmt = (
            select(ViewerLocation)
            .where(ViewerLocation.is_public.is_(True))
            .order_by(kind_order, ViewerLocation.name, ViewerLocation.id)
            .limit(limit)
            .offset(offset)
        )
        if kind is not None:
            stmt = stmt.where(ViewerLocation.kind == kind.value)

        return list((await self.session.execute(stmt)).scalars().all())
