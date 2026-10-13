"""Репозиторий трекеров"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.device import Device
from app.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    """Запросы к трекерам"""

    model = Device

    async def get_for_update(self, device_id: int) -> Device | None:
        stmt = select(Device).where(Device.id == device_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def set_assignment(device: Device, *, participant_id: int | None, stage_id: int | None) -> None:
        device.participant_id = participant_id
        device.stage_id = stage_id

    async def list_for_health(self) -> list[Device]:
        """Получить трекеры в порядке, удобном для админской сводки"""
        stmt = (
            select(Device)
            .options(selectinload(Device.stage))
            .order_by(
                Device.is_active.desc(),
                Device.name.asc(),
                Device.id.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
