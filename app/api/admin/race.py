"""Управление состоянием гонки в административном API"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminDep, SessionDep
from app.db.models.race_status import RaceStatus
from app.db.models.stage import Stage
from app.schemas.admin import RaceStatusResponse, RaceStatusUpdateRequest

router = APIRouter(prefix="/race", tags=["admin-race"])


@router.post("/status", response_model=RaceStatusResponse)
async def update_race_status(
    body: RaceStatusUpdateRequest,
    session: SessionDep,
    _admin: AdminDep,
) -> RaceStatusResponse:
    """Создаем или обновляем текущий статус гонки"""
    if body.current_stage_id is not None:
        stage = await session.get(Stage, body.current_stage_id)
        if stage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Этап не найден",
            )

    race_status = (
        await session.execute(select(RaceStatus).order_by(RaceStatus.id.asc()).limit(1))
    ).scalar_one_or_none()

    if race_status is None:
        race_status = RaceStatus(
            status=body.status.value,
            current_stage_id=body.current_stage_id,
        )
        session.add(race_status)
    else:
        race_status.status = body.status.value
        race_status.current_stage_id = body.current_stage_id

    await session.commit()
    await session.refresh(race_status)

    return RaceStatusResponse.model_validate(race_status)
