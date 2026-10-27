"""Репозиторий трекеров"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models import Participant, Stage, TrackPoint
from app.db.models.device import Device
from app.repositories.base import BaseRepository


@dataclass
class DevicePosition:
    """Активный трекер: связи, последний сигнал, позиция."""

    device_id: int
    iridium_number: str
    device_name: str
    participant_id: int | None
    participant_number: int | None
    participant_name: str | None
    stage_number: int | None
    last_message_at: datetime | None
    lat: float | None
    lon: float | None
    sos_active: bool


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

    async def get_sos_device_mapping(self, participant_ids: list[int]) -> dict[int, int]:
        """Возвращает маппинг participant_id -> device_id для тех, у кого активен SOS."""
        if not participant_ids:
            return {}
        stmt = select(Device.participant_id, Device.id).where(
            Device.sos_active.is_(True),
            Device.participant_id.in_(participant_ids),
        )
        result = await self.session.execute(stmt)
        return {row.participant_id: row.id for row in result.all()}

    async def list_active_with_positions(self, *, only_sos: bool = False) -> list[DevicePosition]:
        """Активные трекеры + участник + этап + последняя позиция (один SQL)."""
        subq = select(
            TrackPoint.device_id,
            TrackPoint.lat,
            TrackPoint.lon,
            func.row_number()
            .over(
                partition_by=TrackPoint.device_id,
                order_by=TrackPoint.recorded_at.desc(),
            )
            .label("rn"),
        ).subquery()

        stmt = (
            select(Device, Participant, Stage, subq.c.lat, subq.c.lon)
            .outerjoin(Participant, Device.participant_id == Participant.id)
            .outerjoin(Stage, Device.stage_id == Stage.id)
            .outerjoin(
                subq,
                (subq.c.device_id == Device.id) & (subq.c.rn == 1),
            )
            .where(Device.is_active.is_(True))
            .order_by(Device.last_message_at.desc().nullslast())
        )
        if only_sos:
            stmt = stmt.where(Device.sos_active.is_(True))

        rows = (await self.session.execute(stmt)).all()

        return [
            DevicePosition(
                device_id=d.id,
                iridium_number=d.iridium_number,
                device_name=d.name,
                participant_id=p.id if p else None,
                participant_number=p.number if p else None,
                participant_name=p.name if p else None,
                stage_number=s.number if s else None,
                last_message_at=d.last_message_at,
                lat=lat,
                lon=lon,
                sos_active=d.sos_active,
            )
            for d, p, s, lat, lon in rows
        ]
