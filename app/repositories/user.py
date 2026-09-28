"""Репозиторий пользователей.

Все запросы к таблице users — здесь.
"""

from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_vk_user_id(self, vk_user_id: int) -> User | None:
        """Найти пользователя по VK ID."""
        stmt = select(User).where(User.vk_user_id == vk_user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
            self,
            *,
            vk_user_id: int,
            first_name: str = "",
            last_name: str = "",
            photo_url: str | None = None,
            platform: str | None = None,
            notifications_allowed: bool = False,
    ) -> User:
        """Создать пользователя. Возвращает объект с заполненным id."""
        user = User(
            vk_user_id=vk_user_id,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            platform=platform,
            notifications_allowed=notifications_allowed,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_from_vk(
            self,
            user: User,
            *,
            first_name: str | None = None,
            last_name: str | None = None,
            photo_url: str | None = None,
            platform: str | None = None,
            notifications_allowed: bool | None = None,
    ) -> User:
        """Обновить поля пользователя из VK.

        Пустые значения (None, "") не перезаписывают существующие —
        чтобы случайно не затереть данные, если VK их не прислал.
        """
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if photo_url:
            user.photo_url = photo_url
        if platform:
            user.platform = platform
        if notifications_allowed is not None:
            user.notifications_allowed = notifications_allowed
        await self.session.flush()
        return user

    async def touch_last_seen(self, user: User) -> None:
        """Обновить время последнего визита."""
        user.last_seen_at = datetime.now(tz=timezone.utc)
        await self.session.flush()

    async def set_notifications_allowed(
            self,
            user_id: int,
            allowed: bool,
    ) -> None:
        """Изменить флаг уведомлений по id (без загрузки объекта)."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(notifications_allowed=allowed)
        )
        await self.session.execute(stmt)
        await self.session.flush()
