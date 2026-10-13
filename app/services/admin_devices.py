from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.device import Device
from app.repositories.device import DeviceRepository
from app.repositories.discipline import DisciplineRepository
from app.repositories.participant import ParticipantRepository
from app.repositories.stage import StageRepository
from app.schemas.admin_devices import DeviceAssignRequest


class AdminDeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.participants = ParticipantRepository(session)
        self.stages = StageRepository(session)
        self.disciplines = DisciplineRepository(session)

    async def assign(self, body: DeviceAssignRequest, *, admin_id: int) -> Device:
        device = await self.devices.get_for_update(body.device_id)
        if device is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Трекер не найден")

        participant = None
        if body.participant_id is not None:
            participant = await self.participants.get_by_id(body.participant_id)
            if participant is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")

        stage = None
        if body.stage_id is not None:
            stage = await self.stages.get_by_id(body.stage_id)
            if stage is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")

        if (
            participant is not None
            and participant.discipline_id is not None
            and stage is not None
            and stage.season_id is not None
        ):
            discipline = await self.disciplines.get_by_id(participant.discipline_id)
            if discipline is None or discipline.season_id != stage.season_id:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Участник и этап относятся к разным сезонам",
                )

        old_assignment = {
            "participant_id": device.participant_id,
            "stage_id": device.stage_id,
        }
        new_assignment = {
            "participant_id": body.participant_id,
            "stage_id": body.stage_id,
        }
        if old_assignment == new_assignment:
            await self.session.commit()
            return device

        self.devices.set_assignment(
            device,
            participant_id=body.participant_id,
            stage_id=body.stage_id,
        )
        self.session.add(
            AuditLog(
                admin_id=admin_id,
                action="device_assignment_changed",
                entity_type="device",
                entity_id=str(device.id),
                payload={"old": old_assignment, "new": new_assignment},
            )
        )
        await self.session.commit()
        await self.session.refresh(device)
        return device
