"""Репозиторий состояния гонки"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.race_status import RaceStatus
from app.enums import RaceState
from app.repositories.base import BaseRepository


class RaceStatusRepository(BaseRepository[RaceStatus]):
    """Запросы к текущему состоянию гонки"""

    model = RaceStatus

    async def get_current(self) -> RaceStatus | None:
        """Получить единственную запись с текущим статусом гонки."""
        stmt = (
            select(RaceStatus)
            .options(selectinload(RaceStatus.current_stage))
            .order_by(RaceStatus.id.asc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def create_current(
        self,
        *,
        status: RaceState,
        current_stage_id: int | None,
    ) -> RaceStatus:
        """Создать текущий статус гонки"""
        return self.add(
            RaceStatus(
                status=status.value,
                current_stage_id=current_stage_id,
            )
        )

    async def update_current(
        self,
        race_status: RaceStatus,
        *,
        status: RaceState,
        current_stage_id: int | None,
    ) -> RaceStatus:
        """Обновить текущий статус гонки"""
        race_status.status = status.value
        race_status.current_stage_id = current_stage_id
        await self.flush()
        return race_status
