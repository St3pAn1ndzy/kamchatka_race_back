"""Репозиторий статичных страниц (О гонке, Правила и т.д.)."""

from sqlalchemy import select

from app.db.models.static_page import StaticPage
from app.repositories.base import BaseRepository


class StaticPageRepository(BaseRepository[StaticPage]):
    """Запросы к статичным страницам."""

    model = StaticPage

    async def get_published_by_slug(self, slug: str) -> StaticPage | None:
        """Публичная страница по slug — только опубликованные."""
        stmt = select(StaticPage).where(
            StaticPage.slug == slug,
            StaticPage.is_published.is_(True),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> StaticPage | None:
        """Страница по slug без фильтра публикации (для админки)."""
        stmt = select(StaticPage).where(StaticPage.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_published(self) -> list[StaticPage]:
        """Все опубликованные страницы (например, для меню «Ещё»)."""
        stmt = select(StaticPage).where(StaticPage.is_published.is_(True)).order_by(StaticPage.slug)
        return list((await self.session.execute(stmt)).scalars().all())
