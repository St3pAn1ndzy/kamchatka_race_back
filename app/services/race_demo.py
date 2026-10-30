"""Локальная имитация трекера для демонстрации движения и SOS"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models.device import Device
from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint
from app.services.cache import cache
from app.services.tracking_metrics import TrackingMetricsService


def check_demo_settings(settings: Settings) -> None:
    """Разрешает запуск только в локальном окружении разработки"""
    if settings.ENV != "dev" or settings.POSTGRES_HOST not in {"localhost", "127.0.0.1"}:
        raise ValueError("Демо разрешено только при ENV=dev с локальной PostgreSQL")


class RaceDemo:
    """Помечает собственные точки и восстанавливает исходное состояние устройства"""

    def __init__(self, session: AsyncSession, device: Device, route: list) -> None:
        self.session = session
        self.device = device
        self.route = [(p.lat, p.lon) for p in route]
        self.assignment = (device.participant_id, device.stage_id)
        self.original = (device.sos_active, device.last_message_at)
        self.run_id = uuid.uuid4().hex
        self.prefix = f"demo:{self.run_id}:"

    @classmethod
    async def prepare(cls, session: AsyncSession, device_id: int) -> "RaceDemo":
        """Проверяет привязку активного трекера и наличие маршрута до записи"""
        device = await session.get(Device, device_id)
        if not device or not device.is_active or not device.participant_id or not device.stage_id:
            raise ValueError("Нужен активный трекер, привязанный к участнику и этапу")
        route = list(
            await session.scalars(
                select(StageRoutePoint)
                .where(StageRoutePoint.stage_id == device.stage_id)
                .order_by(StageRoutePoint.position)
            )
        )
        if len(route) < 2:
            raise ValueError("Сначала загрузите маршрут этапа из двух или более точек")
        latest = await session.scalar(
            select(TrackPoint.recorded_at)
            .where(TrackPoint.device_id == device_id)
            .order_by(TrackPoint.recorded_at.desc())
            .limit(1)
        )
        if latest and latest > datetime.now(UTC):
            raise ValueError("У трекера есть точки из будущего, выберите другой демотрекер")
        return cls(session, device, route)

    async def tick(self, progress: float, *, sos: bool) -> TrackPoint:
        """Добавляет подтверждённую точку на линии и обновляет тревогу трекера"""
        if not 0 <= progress <= 1:
            raise ValueError("Прогресс должен находиться между 0 и 1")
        await self.session.refresh(self.device)
        if (self.device.participant_id, self.device.stage_id) != self.assignment:
            raise ValueError("Привязка трекера изменилась, демонстрация остановлена")
        position = progress * (len(self.route) - 1)
        index = min(int(position), len(self.route) - 2)
        ratio = position - index
        start, end = self.route[index : index + 2]
        marker = self.prefix + uuid.uuid4().hex
        point = TrackPoint(
            device_id=self.device.id,
            participant_id=self.assignment[0],
            stage_id=self.assignment[1],
            lat=start[0] + (end[0] - start[0]) * ratio,
            lon=start[1] + (end[1] - start[1]) * ratio,
            recorded_at=datetime.now(UTC),
            iridium_point_id=marker,
            deduplication_key=hashlib.sha256(marker.encode()).hexdigest(),
            is_confirmed=True,
        )
        await TrackingMetricsService(self.session).fill_metrics(point)
        self.session.add(point)
        self.device.sos_active = sos
        self.device.last_message_at = point.recorded_at
        await self.session.flush()
        return point

    async def cleanup(self) -> None:
        """Удаляет только точки этого запуска и возвращает прежние SOS и время"""
        await self.session.execute(
            delete(TrackPoint).where(
                TrackPoint.device_id == self.device.id,
                TrackPoint.iridium_point_id.startswith(self.prefix),
            )
        )
        await self.session.refresh(self.device)
        self.device.sos_active, self.device.last_message_at = self.original
        await self.session.flush()

    async def invalidate_cache(self) -> None:
        """Обновляет публичные позиции и трек после изменения демонстрационных данных"""
        stage_id = self.assignment[1]
        await cache.invalidate_pattern(f"public:map:model:{stage_id}:*")
        await cache.invalidate_pattern(f"public:map:track:{stage_id}:*")
        await cache.delete(f"public:map:positions:{stage_id}")
        await cache.delete("admin:dashboard:stats")
