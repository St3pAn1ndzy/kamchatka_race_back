from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.faq_item import FAQItem
from app.repositories.base import BaseRepository


class FAQItemRepository(BaseRepository[FAQItem]):
    """Запросы к публичным вопросам - ответам."""

    model = FAQItem

    @staticmethod
    def _public_filters(
        category: str | None,
    ) -> tuple[ColumnElement[bool], ...]:
        """Сформировать одинаковые фильтры для списка и подсчёта."""
        filters: list[ColumnElement[bool]] = [
            FAQItem.is_public.is_(True),
        ]

        if category is not None:
            filters.append(FAQItem.category == category)

        return tuple(filters)

    async def list_public(
        self,
        *,
        category: str | None,
        limit: int,
        offset: int,
    ) -> list[FAQItem]:
        """Получить страницу опубликованных вопросов."""
        stmt = (
            select(FAQItem)
            .where(*self._public_filters(category))
            .order_by(FAQItem.order_index.asc(), FAQItem.id.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_public(self, *, category: str | None) -> int:
        """Посчитать опубликованные вопросы с учётом категории."""
        stmt = select(func.count(FAQItem.id)).where(*self._public_filters(category))
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def get_public_by_id(self, faq_id: int) -> FAQItem | None:
        """Найти опубликованный вопрос по идентификатору."""
        stmt = select(FAQItem).where(
            FAQItem.id == faq_id,
            FAQItem.is_public.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_by_category(self, category: str) -> list[FAQItem]:
        """Все опубликованные вопросы в категории (без пагинации).

        Для страниц, где нужен полный список — «Как добраться», «FAQ».
        """
        stmt = (
            select(FAQItem)
            .where(*self._public_filters(category))
            .order_by(FAQItem.order_index.asc(), FAQItem.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
