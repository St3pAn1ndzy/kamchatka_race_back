"""Сервис управления состоянием гонки в админке"""

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.race_status import RaceStatus
from app.enums import RaceState
from app.repositories.race_status import RaceStatusRepository
from app.repositories.stage import StageRepository


class AdminRaceService:
    """Бизнес-логика управления гонкой для админки"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.race_statuses = RaceStatusRepository(session)
        self.stages = StageRepository(session)

    async def update_status(
        self,
        *,
        admin_id: int,
        status: RaceState,
        current_stage_id: int | None,
    ) -> RaceStatus:
        """Создаём или обновляем текущий статус гонки"""
        if current_stage_id is not None:
            stage_exists = await self.stages.exists_by_id(current_stage_id)
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
            await self.race_statuses.flush()
            action = "race_status_created"
            old_payload = None
        else:
            old_payload = {
                "status": race_status.status,
                "current_stage_id": race_status.current_stage_id,
            }
            race_status = await self.race_statuses.update_current(
                race_status,
                status=status,
                current_stage_id=current_stage_id,
            )
            action = "race_status_updated"

        self.session.add(
            AuditLog(
                admin_id=admin_id,
                action=action,
                entity_type="race_status",
                entity_id=str(race_status.id),
                payload={
                    "old": old_payload,
                    "new": {
                        "status": race_status.status,
                        "current_stage_id": race_status.current_stage_id,
                    },
                },
            )
        )

        await self.session.commit()
        await self.session.refresh(race_status)
        return race_status
