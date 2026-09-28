"""Базовый репозиторий.

Общие методы для всех репозиториев: get_by_id, list, count, add, flush,
commit, delete. Конкретные репозитории наследуются и добавляют
специфичные запросы.

Правило: репозиторий знает ТОЛЬКО про SQLAlchemy и модели.
Никакой бизнес-логики, расчётов, вызовов внешних API.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class BaseRepository[ModelT: Base]:
    """Базовые операции с моделью.

    Конкретный репозиторий задаёт `model`:

        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, obj_id: int) -> ModelT | None:
        """Найти запись по первичному ключу."""
        return await self.session.get(self.model, obj_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """Список записей с пагинацией."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Общее количество записей."""
        stmt = select(func.count()).select_from(self.model)
        return int((await self.session.execute(stmt)).scalar_one())

    def add(self, obj: ModelT) -> ModelT:
        """Добавить объект в сессию (без коммита)."""
        self.session.add(obj)
        return obj

    async def flush(self) -> None:
        """Отправить SQL в БД без коммита. Нужно, чтобы получить id."""
        await self.session.flush()

    async def commit(self) -> None:
        """Зафиксировать транзакцию."""
        await self.session.commit()

    async def delete(self, obj: ModelT) -> None:
        """Удалить объект."""
        await self.session.delete(obj)
