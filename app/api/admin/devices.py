"""Управление трекерами в административном API"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminDep, SessionDep
from app.db.models.device import Device
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.schemas.admin import DeviceAssignRequest, DeviceAssignResponse

router = APIRouter(prefix="/devices", tags=["admin-devices"])


@router.post("/assign", response_model=DeviceAssignResponse)
async def assign_device(
    body: DeviceAssignRequest,
    session: SessionDep,
    _admin: AdminDep,
) -> DeviceAssignResponse:
    """Привязываем трекер к участнику и этапу"""
    device = await session.get(Device, body.device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Трекер не найден",
        )

    if body.participant_id is not None:
        participant = await session.get(Participant, body.participant_id)
        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Участник не найден",
            )

    if body.stage_id is not None:
        stage = await session.get(Stage, body.stage_id)
        if stage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Этап не найден",
            )

    device.participant_id = body.participant_id
    device.stage_id = body.stage_id

    await session.commit()
    await session.refresh(device)

    return DeviceAssignResponse.model_validate(device)
