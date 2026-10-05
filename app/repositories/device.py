"""Репозиторий трекеров"""

from sqlalchemy import select

from app.db.models.device import Device
from app.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    """Запросы к трекерам"""

    model = Device

    async def list_for_health(self) -> list[Device]:
        """Получить трекеры в порядке, удобном для админской сводки"""
        stmt = select(Device).order_by(
            Device.is_active.desc(),
            Device.name.asc(),
            Device.id.asc(),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
