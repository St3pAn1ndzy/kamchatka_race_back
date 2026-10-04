"""Сервис управления состоянием гонки в админке"""

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.race_status import RaceStatus
from app.enums import RaceState
from app.repositories.race_status import RaceStatusRepository


class AdminRaceService:
    """Бизнес-логика управления гонкой для админки"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.race_statuses = RaceStatusRepository(session)

    async def update_status(
        self,
        *,
        status: RaceState,
        current_stage_id: int | None,
    ) -> RaceStatus:
        """Создаём или обновляем текущий статус гонки"""
        if current_stage_id is not None:
            stage_exists = await self.race_statuses.stage_exists(current_stage_id)
            if not stage_exists:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Этап не найден",
                )

        race_status = await self.race_statuses.get_current()
        if race_status is None:
            race_status = self.race_statuses.create_current(
                status=status,
                current_stage_id=current_stage_id,
            )
        else:
            race_status = await self.race_statuses.update_current(
                race_status,
                status=status,
                current_stage_id=current_stage_id,
            )

        await self.session.commit()
        await self.session.refresh(race_status)
        return race_status
