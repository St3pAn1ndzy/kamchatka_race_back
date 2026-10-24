"""Read-only сервис для экрана «Участники» (превью карточек)."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.device import Device
from app.db.models.fun_subscription import FanSubscription
from app.db.models.participant import Participant
from app.services.admin_equipment import get_device_health_status


@dataclass
class ParticipantCard:
    id: int
    number: int
    name: str
    region: str | None
    photo_url: str | None
    bio: str | None
    dogs_count: int | None
    status: str
    discipline_name: str | None
    device_id: int | None
    device_imei: str | None
    fans_count: int
    device_status: str | None


class AdminParticipantService:
    """Данные для просмотра карточек участников."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_participants(self) -> list[ParticipantCard]:
        # Счётчик фанатов
        fan_subq = (
            select(
                FanSubscription.participant_id,
                func.count(FanSubscription.id).label("cnt"),
            )
            .group_by(FanSubscription.participant_id)
            .subquery()
        )

        stmt = (
            select(Participant, Device, fan_subq.c.cnt)
            .outerjoin(Device, Device.participant_id == Participant.id)
            .outerjoin(fan_subq, fan_subq.c.participant_id == Participant.id)
            .options(selectinload(Participant.discipline_ref))
            .order_by(Participant.number)
        )
        rows = (await self.session.execute(stmt)).all()

        result = []
        for p, d, cnt in rows:
            result.append(
                ParticipantCard(
                    id=p.id,
                    number=p.number,
                    name=p.name,
                    region=p.region,
                    photo_url=p.photo_url,
                    bio=p.bio,
                    dogs_count=p.dogs_count,
                    status=p.status,
                    discipline_name=p.discipline_ref.name if p.discipline_ref else None,
                    device_id=d.id if d else None,
                    device_imei=d.imei if d else "",
                    fans_count=cnt or 0,
                    device_status=get_device_health_status(d) if d else None,
                )
            )
        return result

    async def get_participant_detail(self, participant_id: int) -> ParticipantCard | None:
        all_p = await self.get_all_participants()
        for p in all_p:
            if p.id == participant_id:
                return p
        return None
