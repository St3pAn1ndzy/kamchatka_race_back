"""Управление состоянием гонки в административном API"""

from fastapi import APIRouter

from app.api.deps import AdminDep, SessionDep
from app.schemas.admin_race import RaceStatusResponse, RaceStatusUpdateRequest
from app.services.admin_race import AdminRaceService

router = APIRouter(prefix="/race", tags=["admin-race"])


@router.post("/status", response_model=RaceStatusResponse)
async def update_race_status(
    body: RaceStatusUpdateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> RaceStatusResponse:
    """Меняем текущий статус гонки"""
    service = AdminRaceService(session)
    race_status = await service.update_status(
        admin_id=admin.id,
        status=body.status,
        current_stage_id=body.current_stage_id,
    )
    return RaceStatusResponse.model_validate(race_status)
