from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.news_post import NewsPost
from app.repositories.base import BaseRepository


class NewsPostRepository(BaseRepository[NewsPost]):
    """Запросы к опубликованным новостям гонки."""

    model = NewsPost

    @staticmethod
    def _public_filters(
        *,
        source: str | None,
        stage_id: int | None,
        important_only: bool,
        published_from: datetime | None,
        published_to: datetime | None,
        now: datetime,
    ) -> tuple[ColumnElement[bool], ...]:
        """Одинаковые фильтры для списка и корректного total."""
        filters: list[ColumnElement[bool]] = [
            NewsPost.is_published.is_(True),
            NewsPost.published_at.is_not(None),
            NewsPost.published_at <= now,
        ]

        if source is not None:
            filters.append(NewsPost.source == source)
        if stage_id is not None:
            filters.append(NewsPost.stage_id == stage_id)
        if important_only:
            filters.append(NewsPost.is_important.is_(True))
        if published_from is not None:
            filters.append(NewsPost.published_at >= published_from)
        if published_to is not None:
            filters.append(NewsPost.published_at <= published_to)

        return tuple(filters)

    async def list_public(
        self,
        *,
        source: str | None,
        stage_id: int | None,
        important_only: bool,
        published_from: datetime | None,
        published_to: datetime | None,
        now: datetime,
        limit: int,
        offset: int,
    ) -> list[NewsPost]:
        """Получить ленту: закреплённые сверху, затем новые публикации."""
        filters = self._public_filters(
            source=source,
            stage_id=stage_id,
            important_only=important_only,
            published_from=published_from,
            published_to=published_to,
            now=now,
        )
        stmt = (
            select(NewsPost)
            .where(*filters)
            .order_by(
                NewsPost.is_pinned.desc(),
                NewsPost.published_at.desc(),
                NewsPost.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_public(
        self,
        *,
        source: str | None,
        stage_id: int | None,
        important_only: bool,
        published_from: datetime | None,
        published_to: datetime | None,
        now: datetime,
    ) -> int:
        """Посчитать новости с теми же фильтрами, что и list_public."""
        filters = self._public_filters(
            source=source,
            stage_id=stage_id,
            important_only=important_only,
            published_from=published_from,
            published_to=published_to,
            now=now,
        )
        stmt = select(func.count(NewsPost.id)).where(*filters)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def get_public_by_id(self, news_id: int) -> NewsPost | None:
        """Найти опубликованную и уже доступную по времени новость."""
        stmt = select(NewsPost).where(
            NewsPost.id == news_id,
            NewsPost.is_published.is_(True),
            NewsPost.published_at.is_not(None),
            NewsPost.published_at <= datetime.now(tz=UTC),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
